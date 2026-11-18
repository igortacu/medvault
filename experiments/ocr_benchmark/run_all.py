"""Run all prepared local engines in parallel, with bounded model concurrency."""
import argparse
import concurrent.futures
import subprocess
import sys
from pathlib import Path
from compare_runs import compare

CONFIGS = {'tesseract':'tesseract-multilingual.json', 'paddle':'paddle-local-latin.json',
           'docling':'docling-local.json', 'paddle-vl':'paddle-vl-mlx-local.json'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='datasets/smoke/manifest.jsonl')
    parser.add_argument('--output',default='artifacts/parallel-all')
    parser.add_argument('--parallel',type=int,default=2)
    args=parser.parse_args()
    if args.parallel < 1:
        parser.error('--parallel must be positive')
    root=Path(args.output)
    root.mkdir(parents=True,exist_ok=True)
    def execute(item):
        name,config=item
        print(f'START {name}',flush=True)
        with (root/f'{name}.log').open('w') as log:
            process=subprocess.run([sys.executable,'-u','-m','ocrbench','run',
                '--manifest',args.manifest,'--config','configs/'+config,
                '--output',str(root/name),'--workers','1'],stdout=log,stderr=subprocess.STDOUT)
        print(f'END {name} exit={process.returncode}',flush=True)
        return process.returncode
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        codes=list(pool.map(execute,CONFIGS.items()))
    compare(root)
    raise SystemExit(1 if any(codes) else 0)


if __name__ == '__main__':
    main()
