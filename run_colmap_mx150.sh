#!/bin/bash
set -e

echo "=============================="
echo " COLMAP MX150 SAFE PIPELINE"
echo "=============================="

PROJECT_DIR=$(pwd)
IMAGES_DIR="$PROJECT_DIR/images"
DB_PATH="$PROJECT_DIR/database.db"
SPARSE_DIR="$PROJECT_DIR/sparse"
DENSE_DIR="$PROJECT_DIR/dense"

# PEMBERSIHAN AWAL
rm -f "$DB_PATH"
rm -rf "$SPARSE_DIR" "$DENSE_DIR"
mkdir -p "$SPARSE_DIR"
mkdir -p "$DENSE_DIR"

################################
# 1. FEATURE EXTRACTION
################################
echo "[1/6] Feature Extraction (GPU SAFE)"
colmap feature_extractor \
  --database_path "$DB_PATH" \
  --image_path "$IMAGES_DIR" \
  --FeatureExtraction.use_gpu 1 \
  --FeatureExtraction.gpu_index 0 \
  --SiftExtraction.max_image_size 2000 \
  --SiftExtraction.max_num_features 6000

################################
# 2. FEATURE MATCHING
################################
echo "[2/6] Feature Matching (GPU)"
colmap exhaustive_matcher \
  --database_path "$DB_PATH" \
  --FeatureMatching.use_gpu 1 \
  --FeatureMatching.gpu_index 0

################################
# 3. MAPPING
################################
echo "[3/6] Sparse Reconstruction (CPU)"
colmap mapper \
  --database_path "$DB_PATH" \
  --image_path "$IMAGES_DIR" \
  --output_path "$SPARSE_DIR"

################################
# 4. IMAGE UNDISTORTION
################################
echo "[4/6] Image Undistortion"
# Menunggu folder '0' dibuat oleh mapper
if [ -d "$SPARSE_DIR/0" ]; then
    colmap image_undistorter \
      --image_path "$IMAGES_DIR" \
      --input_path "$SPARSE_DIR/0" \
      --output_path "$DENSE_DIR" \
      --output_type COLMAP
else
    echo "Error: Mapper gagal membuat model (folder sparse/0 tidak ditemukan)"
    exit 1
fi

################################
# 5. PATCH MATCH STEREO (MX150 SAFE)
################################
echo "[5/6] Dense Stereo (GPU)"
colmap patch_match_stereo \
  --workspace_path "$DENSE_DIR" \
  --PatchMatchStereo.gpu_index 0 \
  --PatchMatchStereo.max_image_size 1200 \
  --PatchMatchStereo.window_step 2 \
  --PatchMatchStereo.cache_size 16

################################
# 6. DEPTH FUSION
################################
echo "[6/6] Depth Fusion"
colmap stereo_fusion \
  --workspace_path "$DENSE_DIR" \
  --output_path "$DENSE_DIR/fused.ply" \
  --StereoFusion.max_image_size 1200

echo "=============================="
echo " PIPELINE SELESAI 🚀"
echo " Cek file: $DENSE_DIR/fused.ply"
echo "=============================="
