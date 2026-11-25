#!/bin/bash
#SBATCH --job-name=expedition-pages
#SBATCH --partition=ashton
#SBATCH --qos=ashton
#SBATCH --nodelist=grace
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=00:20:00
#SBATCH --chdir=/tmp
set -euo pipefail
script=$1
shift
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="${4}/cache"
mkdir -p "$XDG_CACHE_HOME"
exec "${READER_PYTHON:-python3}" -u "$script" "$@"
