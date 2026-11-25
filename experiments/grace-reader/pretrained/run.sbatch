#!/bin/bash
#SBATCH --job-name=station-hf
#SBATCH --partition=ashton
#SBATCH --qos=ashton
#SBATCH --nodelist=grace
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=00:10:00
#SBATCH --chdir=/tmp
set -euo pipefail
src=$1
weights=$2
out=$3
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export HF_HUB_OFFLINE=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="$out/cache"
mkdir -p "$XDG_CACHE_HOME"
exec "${READER_PYTHON:-python3}" -u "$src/infer.py" "$weights" "$out"
