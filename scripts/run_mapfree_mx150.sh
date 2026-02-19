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
# 1. FEATURE EXTRACTION (BULK, CPU SIFT – STABLE ON MX150)
# -------------------------------------------------
step_feature_extraction() {
  step_done "feature_extractor" && return

  log "=== [1/6] Feature Extraction (bulk, CPU SIFT) ==="

  # Verify paths
  if [ ! -d "$IMAGES_DIR" ]; then
    log_error "Images directory missing: $IMAGES_DIR"
    exit 1
  fi
  nimg=$(find "$IMAGES_DIR" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | wc -l)
  if [ "$nimg" -lt 5 ]; then
    log_error "Too few images in $IMAGES_DIR (found $nimg, need >=5)"
    exit 1
  fi
  log "IMAGES_DIR=$IMAGES_DIR DB_PATH=$DB_PATH (images: $nimg)"

  rm -f "$DB_PATH"

  # Bulk extraction: entire folder at once. CPU via FeatureExtraction.* for stability.
  # Output is shown (tee) so COLMAP stderr is visible when it fails.
  log "Running: colmap feature_extractor (CPU, bulk)..."
  colmap feature_extractor \
    --database_path "$DB_PATH" \
    --image_path "$IMAGES_DIR" \
    --ImageReader.camera_model OPENCV \
    --ImageReader.single_camera 1 \
    --FeatureExtraction.use_gpu 0 \
    --FeatureExtraction.gpu_index -1 \
    --FeatureExtraction.num_threads 4 \
    --FeatureExtraction.max_image_size 2000 \
    --SiftExtraction.max_num_features 4096 \
    2>&1 | tee -a "$LOG_FILE"
  exc=${PIPESTATUS[0]}
  if [ "$exc" -eq 0 ]; then
    log "Feature extraction OK (CPU, bulk)"
    mark_done "feature_extractor"
    return
  fi
  log_error "Feature extraction failed (exit $exc). See COLMAP stderr above."
  exit 1
}

# -------------------------------------------------
# 2. FEATURE MATCHING (GPU SAFE, FALLBACK CPU)
# -------------------------------------------------
step_feature_matching() {
  step_done "matcher" && return

  log "=== [2/6] Feature Matching (exhaustive, CPU) ==="
  # Exhaustive: no GPS required (spatial_matcher gave "No images with location data")
  # COLMAP 3.14 uses FeatureMatching.*; use_gpu=0 for CPU
  colmap exhaustive_matcher \
    --database_path "$DB_PATH" \
    --FeatureMatching.use_gpu 0 \
    --FeatureMatching.gpu_index -1 \
    --FeatureMatching.num_threads "${NUM_THREADS:-4}" \
    >> "$LOG_FILE" 2>&1 || exit 1

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
# 5. PATCH MATCH STEREO (WebODM-style: 800px, geom_consistency=0, GPU→CPU fallback)
# Note: Some COLMAP builds are CUDA-only for dense; without GPU this step fails.
# -------------------------------------------------
step_dense() {
  step_done dense && return

  log "=== [5/6] PatchMatch Stereo (max_image_size=800, geom_consistency=0) ==="

  if colmap patch_match_stereo \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index 0 \
    --PatchMatchStereo.max_image_size 800 \
    --PatchMatchStereo.cache_size 8 \
    --PatchMatchStereo.window_step 2 \
    --PatchMatchStereo.geom_consistency 0 \
    >> "$LOG_FILE" 2>&1; then
    mark_done dense
    return
  fi

  log_fallback "PatchMatch GPU failed → CPU fallback (same safe params)"
  # Hide GPU so COLMAP uses CPU path (else it still init CUDA and fail)
  if ! CUDA_VISIBLE_DEVICES="" colmap patch_match_stereo \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index -1 \
    --PatchMatchStereo.max_image_size 800 \
    --PatchMatchStereo.cache_size 8 \
    --PatchMatchStereo.window_step 2 \
    --PatchMatchStereo.geom_consistency 0 \
    >> "$LOG_FILE" 2>&1; then
    log_error "PatchMatch stereo failed (GPU and CPU fallback)"
    log_error "If you see 'no CUDA-capable device': this COLMAP build may be CUDA-only for dense; run on a machine with GPU or build COLMAP with CPU stereo."
    exit 1
  fi

  mark_done dense
}

# -------------------------------------------------
# 6. FUSION (max_image_size=800 for MX150 VRAM)
# -------------------------------------------------
step_fusion() {
  step_done fusion && return

  log "=== [6/6] Stereo Fusion (max_image_size=800) ==="

  if ! colmap stereo_fusion \
    --workspace_path "$DENSE_DIR" \
    --workspace_format COLMAP \
    --input_type geometric \
    --output_path "$DENSE_DIR/fused.ply" \
    --StereoFusion.max_image_size 800 \
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
