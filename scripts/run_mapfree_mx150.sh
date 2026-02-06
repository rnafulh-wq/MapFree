#!/usr/bin/env bash
#
# MapFree MX150 SAFE Pipeline
# GPU: NVIDIA MX150 (2GB VRAM, Pascal CC 6.1)
# Priority: Stability > Completeness > Speed
#
set -e

# ==== MX150 CUDA SAFETY ====
export CUDA_VISIBLE_DEVICES=0
export CUDA_LAUNCH_BLOCKING=1
export CUDA_DEVICE_MAX_CONNECTIONS=1
export OMP_NUM_THREADS=2

GPU_ERROR_PATTERN="illegal memory access|Failed to process image|No images with matches|CUDA error|out of memory"

PROJECT_DIR=
IMAGES_DIR=
LOG_FILE=
DB_PATH=
SPARSE_DIR=
DENSE_DIR=

log()        { echo "[`date '+%F %T'`] $*" | tee -a "$LOG_FILE"; }
log_error()  { echo "[`date '+%F %T'`] ERROR: $*" | tee -a "$LOG_FILE" >&2; }
log_fallback(){ echo "[`date '+%F %T'`] FALLBACK: $*" | tee -a "$LOG_FILE" >&2; }

run_and_check() {
  local desc="$1"; shift
  local out; out=$(mktemp)

  log "RUN: $desc"
  log "CMD: $*"

  if "$@" > "$out" 2>&1; then
    if grep -qiE "$GPU_ERROR_PATTERN" "$out"; then
      cat "$out" >> "$LOG_FILE"
      log_error "GPU keyword detected in step: $desc"
      rm -f "$out"
      return 1
    fi
    cat "$out" >> "$LOG_FILE"
    rm -f "$out"
    return 0
  fi

  cat "$out" >> "$LOG_FILE"
  rm -f "$out"
  return 1
}

setup_project() {
  if [ -n "$1" ] && [ -n "$2" ]; then
    ROOT="$(cd "$(dirname "$0")/.." && pwd)"
    PROJECT_DIR="$ROOT/projects/$2"
    IMAGES_DIR="$PROJECT_DIR/images"
    mkdir -p "$IMAGES_DIR"
    cp -n "$1"/*.{jpg,JPG,jpeg,JPEG,png,PNG} "$IMAGES_DIR/" 2>/dev/null || true
  else
    PROJECT_DIR=$(pwd)
    IMAGES_DIR="$PROJECT_DIR/images"
  fi

  LOG_FILE="$PROJECT_DIR/mapfree.log"
  DB_PATH="$PROJECT_DIR/database.db"
  SPARSE_DIR="$PROJECT_DIR/sparse"
  DENSE_DIR="$PROJECT_DIR/dense"

  mkdir -p "$SPARSE_DIR" "$DENSE_DIR"

  # When we copied from an input dir, validate count (same extensions as copy: include .jpeg/.JPEG)
  if [ -n "$1" ] && [ -n "$2" ]; then
    NIMG=$(find "$IMAGES_DIR" -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.JPG' -o -name '*.jpeg' -o -name '*.JPEG' -o -name '*.png' -o -name '*.PNG' \) | wc -l)
    if [ "$NIMG" -lt 3 ]; then
      log_error "Not enough images in $1 (found $NIMG, need at least 3)"
      exit 1
    fi
  fi
}

step_done() { [ -f "$PROJECT_DIR/.done_$1" ]; }
mark_done() { touch "$PROJECT_DIR/.done_$1"; }

# -------------------------------------------------
# 1. FEATURE EXTRACTION (GPU SIFT-ONLY, PER-IMAGE, DB APPEND)
# -------------------------------------------------
step_feature_extraction() {
  step_done "feature_extractor" && return

  log "=== [1/6] Feature Extraction (GPU SIFT-only, per-image) ==="

  rm -f "$DB_PATH"

  success=0
  failed=0

  while IFS= read -r img; do
    name=$(basename "$img")
    tmpdir=$(mktemp -d)

    ln -s "$img" "$tmpdir/$name" 2>/dev/null || cp "$img" "$tmpdir/$name"

    log "SIFT GPU: $name"

    if colmap feature_extractor \
      --database_path "$DB_PATH" \
      --image_path "$tmpdir" \
      --ImageReader.camera_model OPENCV \
      --ImageReader.single_camera 1 \
      --SiftExtraction.use_gpu 1 \
      --SiftExtraction.gpu_index 0 \
      --SiftExtraction.max_image_size 1600 \
      --SiftExtraction.max_num_features 4096 \
      --SiftExtraction.num_threads 1 \
      >> "$LOG_FILE" 2>&1; then

      success=$((success+1))
      log "OK GPU: $name"

    else
      log_fallback "GPU failed → CPU SIFT: $name"

      if colmap feature_extractor \
        --database_path "$DB_PATH" \
        --image_path "$tmpdir" \
        --ImageReader.camera_model OPENCV \
        --ImageReader.single_camera 1 \
        --SiftExtraction.use_gpu 0 \
        --SiftExtraction.max_image_size 1200 \
        --SiftExtraction.max_num_features 4096 \
        --SiftExtraction.num_threads 1 \
        >> "$LOG_FILE" 2>&1; then

        success=$((success+1))
        log "OK CPU: $name"
      else
        failed=$((failed+1))
        log_error "SKIP image: $name"
      fi
    fi

    rm -rf "$tmpdir"

  done < <(find "$IMAGES_DIR" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | sort)

  log "Feature extraction done: success=$success failed=$failed"

  if [ "$success" -lt 5 ]; then
    log_error "Too few images with features (need >=5)"
    exit 1
  fi

  mark_done "feature_extractor"
}

# -------------------------------------------------
# 2. FEATURE MATCHING (GPU SAFE, FALLBACK CPU)
# -------------------------------------------------
step_feature_matching() {
  step_done "matcher" && return

  log "=== [2/6] Feature Matching (GPU safe) ==="

  if ! colmap spatial_matcher \
    --database_path "$DB_PATH" \
    --SiftMatching.use_gpu 1 \
    --SiftMatching.gpu_index 0 \
    --SiftMatching.num_threads 1 \
    >> "$LOG_FILE" 2>&1; then

    log_fallback "Matching GPU failed → CPU"

    colmap spatial_matcher \
      --database_path "$DB_PATH" \
      --SiftMatching.use_gpu 0 \
      --SiftMatching.num_threads 1 \
      >> "$LOG_FILE" 2>&1 || exit 1
  fi

  mark_done "matcher"
}

# -------------------------------------------------
# 3. SPARSE RECONSTRUCTION (CPU ONLY)
# -------------------------------------------------
step_sparse() {
  step_done sparse && return

  log "=== [3/6] Sparse Reconstruction ==="

  colmap mapper \
    --database_path "$DB_PATH" \
    --image_path "$IMAGES_DIR" \
    --output_path "$SPARSE_DIR" \
    >> "$LOG_FILE" 2>&1

  [ ! -d "$SPARSE_DIR/0" ] && log_error "Sparse model missing" && exit 1
  mark_done sparse
}

# -------------------------------------------------
# 4. UNDISTORTION
# -------------------------------------------------
step_undistort() {
  step_done undistort && return

  log "=== [4/6] Image Undistortion ==="

  if ! colmap image_undistorter \
    --image_path "$IMAGES_DIR" \
    --input_path "$SPARSE_DIR/0" \
    --output_path "$DENSE_DIR" \
    --output_type COLMAP \
    >> "$LOG_FILE" 2>&1; then
    log_error "Image undistortion failed"
    exit 1
  fi

  mark_done undistort
}

# -------------------------------------------------
# 5. PATCH MATCH STEREO (CPU ONLY – MX150 STABLE)
# -------------------------------------------------
step_dense() {
  step_done dense && return

  log "=== [5/6] PatchMatch Stereo (CPU only) ==="

  if ! colmap patch_match_stereo \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index -1 \
    --PatchMatchStereo.max_image_size 1000 \
    --PatchMatchStereo.cache_size 8 \
    --PatchMatchStereo.window_step 2 \
    >> "$LOG_FILE" 2>&1; then
    log_error "PatchMatch stereo failed"
    exit 1
  fi

  mark_done dense
}

# -------------------------------------------------
# 6. FUSION
# -------------------------------------------------
step_fusion() {
  step_done fusion && return

  log "=== [6/6] Stereo Fusion ==="

  if ! colmap stereo_fusion \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --input_type geometric \
    --output_path "$DENSE_DIR/fused.ply" \
    >> "$LOG_FILE" 2>&1; then
    log_error "Stereo fusion failed"
    exit 1
  fi

  mark_done fusion
}

# -------------------------------------------------
main() {
  setup_project "$@"
  log "=== MapFree MX150 SAFE PIPELINE START ==="

  rm -f "$DB_PATH"
  step_feature_extraction
  step_feature_matching
  step_sparse
  step_undistort
  step_dense
  step_fusion

  log "=== PIPELINE FINISHED ==="
  log "Output: $DENSE_DIR/fused.ply"
}
main "$@"
