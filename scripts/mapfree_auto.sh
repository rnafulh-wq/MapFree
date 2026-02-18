#!/usr/bin/env bash

set -e

IMAGE_PATH=$1
PROJECT_DIR=$2

if [ -z "$IMAGE_PATH" ] || [ -z "$PROJECT_DIR" ]; then
  echo "Usage: ./mapfree_auto.sh <image_folder> <project_output>"
  exit 1
fi

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

echo "🔍 Detecting GPU..."

if command -v nvidia-smi &> /dev/null; then
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n1)
else
    echo "❌ No NVIDIA GPU detected. Switching to CPU mode."
    VRAM=0
fi

echo "Detected VRAM: ${VRAM} MB"

# Default safe fallback
MAX_IMAGE_SIZE=1200
MAX_FEATURES=5000
MATCHER="sequential"
USE_GPU=0

if [ "$VRAM" -ge 4096 ]; then
    PROFILE="HIGH"
    MAX_IMAGE_SIZE=2400
    MAX_FEATURES=20000
    MATCHER="exhaustive"
    USE_GPU=1
elif [ "$VRAM" -ge 2048 ]; then
    PROFILE="MEDIUM"
    MAX_IMAGE_SIZE=2000
    MAX_FEATURES=12000
    MATCHER="exhaustive"
    USE_GPU=1
elif [ "$VRAM" -ge 1024 ]; then
    PROFILE="LOW"
    MAX_IMAGE_SIZE=1600
    MAX_FEATURES=8000
    MATCHER="sequential"
    USE_GPU=1
else
    PROFILE="CPU_SAFE"
fi

echo "Using profile: $PROFILE"
echo "Max image size: $MAX_IMAGE_SIZE"
echo "Max features: $MAX_FEATURES"
echo "Matcher: $MATCHER"

########################################
# 1️⃣ Feature Extraction
########################################

colmap feature_extractor \
  --database_path database.db \
  --image_path "$IMAGE_PATH" \
  --ImageReader.single_camera 1 \
  --FeatureExtraction.use_gpu $USE_GPU \
  --FeatureExtraction.max_image_size $MAX_IMAGE_SIZE \
  --SiftExtraction.max_num_features $MAX_FEATURES \
  --SiftExtraction.first_octave -1 \
  --SiftExtraction.peak_threshold 0.006

########################################
# 2️⃣ Matching
########################################

if [ "$MATCHER" = "exhaustive" ]; then
    colmap exhaustive_matcher \
      --database_path database.db \
      --FeatureMatching.use_gpu $USE_GPU
else
    colmap sequential_matcher \
      --database_path database.db \
      --FeatureMatching.use_gpu $USE_GPU
fi

########################################
# 3️⃣ Sparse Reconstruction
########################################

colmap mapper \
  --database_path database.db \
  --image_path "$IMAGE_PATH" \
  --output_path sparse \
  --Mapper.ba_global_max_num_iterations 30 \
  --Mapper.ba_local_max_num_iterations 20

########################################
# 4️⃣ Dense Reconstruction
########################################

colmap image_undistorter \
  --image_path "$IMAGE_PATH" \
  --input_path sparse/0 \
  --output_path dense \
  --output_type COLMAP \
  --max_image_size $MAX_IMAGE_SIZE

colmap patch_match_stereo \
  --workspace_path dense \
  --workspace_format COLMAP \
  --PatchMatchStereo.geom_consistency true \
  --PatchMatchStereo.max_image_size $MAX_IMAGE_SIZE \
  --PatchMatchStereo.window_radius 4 \
  --PatchMatchStereo.num_samples 10

colmap stereo_fusion \
  --workspace_path dense \
  --workspace_format COLMAP \
  --input_type geometric \
  --output_path dense/fused.ply

echo "✅ Reconstruction finished."
