#!/usr/bin/env bash
#
# MapFree MX150 SAFE Pipeline
# GPU: NVIDIA MX150 (2GB VRAM, Pascal CC 6.1)
# Priority: Stability > Completeness > Speed
#
set -e

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
  export OMP_NUM_THREADS=4

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
# 1. FEATURE EXTRACTION (PER-IMAGE, GPU → CPU FALLBACK, SKIP FAILED)
# -------------------------------------------------
step_feature_extraction() {
  step_done fe && return

  log "=== [1/6] Feature Extraction (per-image, skip on failure) ==="

  rm -f "$DB_PATH"

  success_count=0
  failed_count=0
  total=0

  while IFS= read -r fullpath; do
    [ -z "$fullpath" ] && continue
    img=$(basename "$fullpath")
    total=$((total + 1))
    TMPDIR=$(mktemp -d)
    ln -s "$fullpath" "$TMPDIR/$img" 2>/dev/null || cp "$fullpath" "$TMPDIR/$img"

    if run_and_check "Feature Extraction GPU [$img]" colmap feature_extractor \
      --database_path "$DB_PATH" \
      --image_path "$TMPDIR" \
      --ImageReader.camera_model OPENCV \
      --SiftExtraction.use_gpu 1 \
      --SiftExtraction.gpu_index 0 \
      --SiftExtraction.max_image_size 2000 \
      --SiftExtraction.max_num_features 4096 \
      --SiftExtraction.num_threads 2; then
      success_count=$((success_count + 1))
      log "SUCCESS image: $img"
    else
      log_fallback "GPU failed for $img → CPU fallback"
      if colmap feature_extractor \
        --database_path "$DB_PATH" \
        --image_path "$TMPDIR" \
        --ImageReader.camera_model OPENCV \
        --SiftExtraction.use_gpu 0 \
        --SiftExtraction.max_image_size 1600 \
        --SiftExtraction.max_num_features 4096 \
        --SiftExtraction.num_threads 2 \
        >> "$LOG_FILE" 2>&1; then
        success_count=$((success_count + 1))
        log "SUCCESS image (CPU): $img"
      else
        failed_count=$((failed_count + 1))
        log "SKIP image: $img"
      fi
    fi
    rm -rf "$TMPDIR"
  done < <(find "$IMAGES_DIR" -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.JPG' -o -name '*.jpeg' -o -name '*.JPEG' -o -name '*.png' -o -name '*.PNG' \) | sort)

  log "Feature extraction: success=$success_count failed=$failed_count total=$total"

  if [ "$success_count" -lt 5 ]; then
    log_error "Too few images with features (success=$success_count, need >= 5). Abort pipeline."
    exit 1
  fi

  mark_done fe
}

# -------------------------------------------------
# 2. FEATURE MATCHING (SPATIAL → EXHAUSTIVE FALLBACK)
# -------------------------------------------------
step_matching() {
  step_done match && return

  log "=== [2/6] Feature Matching ==="

  if ! run_and_check "Spatial Matcher GPU" colmap spatial_matcher \
    --database_path "$DB_PATH" \
    --SiftMatching.use_gpu 1 \
    --SiftMatching.gpu_index 0; then
    log_fallback "Spatial GPU failed → CPU"
    if ! colmap spatial_matcher \
      --database_path "$DB_PATH" \
      --SiftMatching.use_gpu 0 \
      >> "$LOG_FILE" 2>&1; then
      log_error "Spatial matcher failed (GPU and CPU fallback)"
      exit 1
    fi
  fi

  MATCHED_IMAGES=$(sqlite3 "$DB_PATH" "SELECT COUNT(DISTINCT image_id) FROM inlier_matches;" 2>/dev/null || echo 0)
  log "Matched images (inlier_matches): $MATCHED_IMAGES"

  if [ "$MATCHED_IMAGES" -lt 2 ]; then
    log_fallback "Not enough verified matches → exhaustive CPU matcher"
    if ! colmap exhaustive_matcher \
      --database_path "$DB_PATH" \
      --SiftMatching.use_gpu 0 \
      >> "$LOG_FILE" 2>&1; then
      log_error "Exhaustive matcher failed"
      exit 1
    fi
  fi

  MATCHED_IMAGES=$(sqlite3 "$DB_PATH" "SELECT COUNT(DISTINCT image_id) FROM inlier_matches;" 2>/dev/null || echo 0)
  [ "$MATCHED_IMAGES" -lt 2 ] && log_error "Not enough matched images after fallback" && exit 1

  mark_done match
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
# 5. PATCH MATCH STEREO (GPU SAFE MODE)
# -------------------------------------------------
step_dense() {
  step_done dense && return

  log "=== [5/6] PatchMatch Stereo ==="

  if run_and_check "PatchMatch GPU" colmap patch_match_stereo \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index 0 \
    --PatchMatchStereo.max_image_size 1100 \
    --PatchMatchStereo.window_step 2 \
    --PatchMatchStereo.num_iterations 2 \
    --PatchMatchStereo.geom_consistency 0 \
    --PatchMatchStereo.filter 1 \
    --PatchMatchStereo.cache_size 12; then
    mark_done dense; return
  fi

  log_fallback "PatchMatch GPU failed → CPU fallback"

  if ! colmap patch_match_stereo \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index -1 \
    --PatchMatchStereo.max_image_size 1000 \
    >> "$LOG_FILE" 2>&1; then
    log_error "PatchMatch stereo failed (GPU and CPU fallback)"
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
  step_matching
  step_sparse
  step_undistort
  step_dense
  step_fusion

  log "=== PIPELINE FINISHED ==="
  log "Output: $DENSE_DIR/fused.ply"
}
main "$@"
