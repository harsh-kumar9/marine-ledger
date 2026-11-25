#!/bin/bash
#SBATCH --job-name=station-ctc
#SBATCH --partition=ashton
#SBATCH --qos=ashton
#SBATCH --nodelist=grace
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:15:00
#SBATCH --chdir=/tmp
#SBATCH --requeue
set -euo pipefail
# Submit with an absolute --output and arguments: WORKSPACE OUTPUT STAGE.
reader_root=$1
run_dir=$2
stage=$3
cd "$reader_root"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export XDG_CACHE_HOME="$run_dir/cache" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
mkdir -p "$XDG_CACHE_HOME"
case "$stage" in
    pretrain) marker="$run_dir/pretrain-result.json" ;;
    adapt) marker="$run_dir/freeze.json" ;;
    predict) marker="$run_dir/adapted-test.jsonl" ;;
    *) exit 2 ;;
esac
if [[ -f "$marker" ]]; then
    echo "Completed stage found: $marker"
    exit 0
fi
hostname
date -u
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
exec "${READER_PYTHON:-python3}" -u reader.py "$stage" --out "$run_dir"
