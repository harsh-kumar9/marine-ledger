"""Train, freeze and apply a small CTC reader to printed station identifier crops."""

import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import re
import string

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import torch
from torch import nn


ALPHABET = string.digits + string.ascii_uppercase
ENCODE = {s: i + 1 for i, s in enumerate(ALPHABET)}
HEIGHT, WIDTH = 32, 160
ROOT = Path(__file__).resolve().parent
CONFIG = {
    'seed': 1776, 'batch_size': 48, 'synthetic_examples': 12288, 'pretrain_steps': 2200,
    'adapt_steps': 240, 'validate_every': 20, 'pretrain_lr': 0.0014, 'adapt_lr': 0.00025,
    'real_fraction': 0.67, 'decoder': 'CTC greedy, collapse repeats before dropping blanks',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def save_weights(path, model):
    tmp = path.with_suffix('.tmp')
    torch.save({'weights': model.state_dict(), 'alphabet': ALPHABET, 'config': CONFIG}, tmp)
    tmp.replace(path)


def get_weights(path, device):
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    if checkpoint['alphabet'] != ALPHABET:
        raise ValueError('checkpoint alphabet mismatch')
    model = Reader().to(device)
    model.load_state_dict(checkpoint['weights'])
    return model


def fonts():
    # Explicit family allowlist. Use the same installed fonts in the reference run.
    stems = ('DejaVuSerif', 'DejaVuSans', 'LiberationSerif', 'LiberationSans', 'LiberationMono', 'cmr10')
    dirs = [Path('/usr/share/fonts'), Path('/usr/local/share/fonts')]
    try:
        import matplotlib
        dirs.append(Path(matplotlib.get_data_path()) / 'fonts/ttf')
    except ImportError:
        pass
    by_name = {}
    for directory in dirs:
        for file in sorted(directory.rglob('*.ttf')):
            if file.stem.startswith(stems) and 'Math' not in file.stem:
                by_name.setdefault(file.name, file)
    if not by_name:
        raise RuntimeError('install DejaVu or Liberation TrueType fonts')
    return [by_name[name] for name in sorted(by_name)]


@lru_cache(maxsize=300)
def font_at(path, size):
    return ImageFont.truetype(str(path), size)


def prepare(image):
    gray = np.array(image.convert('L'), dtype=np.float32)
    background = float(np.percentile(gray, 87))
    dark = float(gray.min())
    # Normalize ink contrast; bound outliers when determining the retained edges.
    ink = np.clip((background - gray) / max(background - dark, 12), 0, 1)
    mask = ink > 0.28
    h, w = mask.shape
    for axis, size in ((0, w), (1, h)):
        covered = mask.mean(axis=axis)
        index = np.arange(size)
        ruling = (covered > .80) & ((index < size * .12) | (index > size * .88))
        if axis == 0:
            mask[:, ruling] = False
            ink[:, ruling] = 0
        else:
            mask[ruling, :] = False
            ink[ruling, :] = 0
    y, x = np.where(mask)
    if len(x):
        ink = ink[y.min():y.max()+1, x.min():x.max()+1]
    h, w = ink.shape
    scale = min(26 / h, (WIDTH - 12) / w)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    resized = Image.fromarray(np.uint8(ink * 255)).resize((nw, nh), Image.Resampling.BILINEAR)
    field = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    top = (HEIGHT - nh) // 2
    field[top:top+nh, 4:4+nw] = np.asarray(resized)
    return field, (nw + 11) // 4


def synthetic(rng, available):
    digits = ''.join(rng.choice(list(string.digits), size=int(rng.integers(1, 6))))
    prefix, suffix = '', ''
    if rng.random() < .23:
        prefix = str(rng.choice(list(string.ascii_uppercase)))
    if rng.random() < .16:
        suffix = str(rng.choice(list(string.ascii_uppercase)))
    value = prefix + digits + suffix
    printed = prefix
    if prefix:
        printed += str(rng.choice(['', '', ' ', '. ', '-']))
    printed += digits
    if suffix:
        printed += str(rng.choice(['', '', ' ']))
        printed += suffix.lower() if rng.random() < .5 else suffix
    size = int(rng.integers(18, 43))
    font = font_at(available[int(rng.integers(len(available)))], size)
    left, top, right, bottom = font.getbbox(printed)
    bg = int(rng.integers(179, 256))
    color = int(rng.integers(5, 111))
    image = Image.new('L', (max(2, right-left+12), max(4, bottom-top+10)), bg)
    draw = ImageDraw.Draw(image)
    draw.text((6-left, 5-top), printed, fill=color, font=font)
    if rng.random() < .45:
        image = image.rotate(rng.uniform(-2.5, 2.5), resample=Image.Resampling.BILINEAR, fillcolor=bg)
    if rng.random() < .45:
        image = image.filter(ImageFilter.GaussianBlur(float(rng.uniform(.15, 1.15))))
    if rng.random() < .3:
        image = image.resize((max(6, int(image.width*rng.uniform(.7,1.2))), image.height), Image.Resampling.BILINEAR)
    array = np.asarray(image, dtype=np.float32)
    array += rng.normal(0, rng.uniform(0,9), size=array.shape)
    return (*prepare(Image.fromarray(np.clip(array,0,255).astype(np.uint8))), str(value))


class Reader(nn.Module):
    def __init__(self):
        super().__init__()
        layers = []
        for a, b, pool in [(1, 32, (2,2)), (32, 48, (2,2)), (48, 64, (2,1)), (64, 96, (2,1))]:
            layers.extend([nn.Conv2d(a,b,3,padding=1), nn.BatchNorm2d(b), nn.ReLU(), nn.MaxPool2d(pool)])
        self.features = nn.Sequential(*layers)
        self.context = nn.GRU(96, 64, batch_first=True, bidirectional=True)
        self.head = nn.Linear(128, len(ALPHABET) + 1)

    def forward(self, images):
        horizontal = self.features(images).mean(dim=2).transpose(1,2)
        contextual, _ = self.context(horizontal)
        return self.head(contextual).log_softmax(-1)


def decode(logits, lengths):
    predictions = []
    for path, length in zip(logits.argmax(-1).tolist(), lengths):
        symbols = [ch for i, ch in enumerate(path[:length]) if ch and (i == 0 or ch != path[i-1])]
        predictions.append(''.join(ALPHABET[ch-1] for ch in symbols))
    return predictions


def distance(left, right):
    prev = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        row = [i]
        for j, b in enumerate(right, 1):
            row.append(min(row[-1]+1, prev[j]+1, prev[j-1]+(a != b)))
        prev = row
    return prev[-1]


def measure(reference, predictions):
    if len(reference) != len(predictions) or not reference:
        raise ValueError('empty or mismatched evaluation')
    groups = defaultdict(list)
    for row, predicted in zip(reference, predictions):
        groups[row['expedition']].append((row['text'], predicted))
    counts = {}
    for group, pairs in groups.items():
        counts[group] = {'exact':sum(a==b for a,b in pairs), 'n':len(pairs),
                         'edits':sum(distance(a,b) for a,b in pairs), 'chars':sum(len(a) for a,b in pairs)}
    return {'exact':sum(v['exact']/v['n'] for v in counts.values())/len(counts),
            'cer':sum(v['edits']/v['chars'] for v in counts.values())/len(counts), 'counts':counts}


def load_rows(path, labeled):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows or len({row['id'] for row in rows}) != len(rows):
        raise ValueError(f'empty or duplicate station crops: {path}')
    images = []
    for row in rows:
        if ('text' in row) != labeled:
            raise ValueError(f'unexpected label availability in {path}')
        label = row.get('text', '')
        if labeled and not re.fullmatch('[0-9A-Z]+', label):
            raise ValueError(f'noncanonical label in {path}')
        with Image.open(ROOT / row['image']) as image:
            images.append((*prepare(image), label))
    return rows, images


def tensor_batch(batch, device, augment=False):
    images = torch.from_numpy(np.stack([e[0] for e in batch])).to(device).float().unsqueeze(1) / 255
    if augment:
        # Mimic changes in print density and vertical registration; labels stay unchanged.
        n = len(batch)
        images *= (.75 + .5*torch.rand(n,1,1,1,device=device))
        images = (images + .035 * torch.randn_like(images)).clamp(0,1)
        images = torch.roll(images, shifts=random.choice([-1,0,1]), dims=2)
    return images, [e[1] for e in batch]


def fit_batch(model, optimizer, batch, device):
    model.train()
    optimizer.zero_grad(set_to_none=True)
    images, lengths = tensor_batch(batch,device,True)
    outputs = model(images).transpose(0,1)
    targets = [torch.tensor([ENCODE[ch] for ch in row[2]], dtype=torch.long) for row in batch]
    loss = nn.functional.ctc_loss(outputs, torch.cat(targets), lengths, [len(t) for t in targets],
                                  blank=0, zero_infinity=False)
    if not torch.isfinite(loss):
        raise ValueError('nonfinite CTC loss; check image widths and label lengths')
    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), 2.0)
    optimizer.step()
    return float(loss.detach())


@torch.no_grad()
def predict(model, examples, device):
    model.eval()
    out = []
    for start in range(0,len(examples),CONFIG['batch_size']):
        images,lengths = tensor_batch(examples[start:start+CONFIG['batch_size']],device)
        out.extend(decode(model(images),lengths))
    return out


def synthetic_set(size, seed, available):
    rng = np.random.default_rng(seed)
    return [synthetic(rng,available) for _ in range(size)]


def run(args):
    seed = CONFIG['seed']
    torch.manual_seed(seed)
    random.seed(seed)
    torch.set_num_threads(2)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if args.action != 'predict' and device.type != 'cuda':
        raise RuntimeError('training requires a scheduled CUDA device')
    out = args.out
    out.mkdir(exist_ok=True, parents=True)
    if args.action == 'predict':
        rows, images = load_rows(args.manifest,False)
        for stage in ('synthetic','adapted'):
            path = out / (stage + '.pt')
            meta = json.loads((out/'freeze.json').read_text())
            if sha(path) != meta['checkpoint_sha256'][stage]:
                raise ValueError('frozen checkpoint hash mismatch')
            predictions = predict(get_weights(path,device), images, device)
            destination = out / (stage + '-test.jsonl')
            temp = destination.with_suffix('.tmp')
            with temp.open('w') as handle:
                for row, text in zip(rows, predictions):
                    handle.write(json.dumps({'id':row['id'], 'text':text}) + '\n')
            temp.replace(destination)
        return
    available = fonts()
    print('device', torch.cuda.get_device_name(), 'torch',torch.__version__, 'fonts',len(available), flush=True)
    if args.action == 'pretrain':
        write_json(out/'pretrain-config.json', {'configuration':CONFIG, 'fonts':{p.name:sha(p) for p in available},
                                              'torch':torch.__version__, 'device':torch.cuda.get_device_name()})
        synthetic_train = synthetic_set(CONFIG['synthetic_examples'],seed,available)
        synthetic_val = synthetic_set(160,seed+1,available)
        refs = [{'text':e[2],'expedition':'generated'} for e in synthetic_val]
        model = Reader().to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG['pretrain_lr'])
        schedule = torch.optim.lr_scheduler.MultiStepLR(optimizer, milestones=[1400, 1900], gamma=.4)
        for step in range(1, CONFIG['pretrain_steps'] + 1):
            loss = fit_batch(model,optimizer,random.choices(synthetic_train,k=CONFIG['batch_size']),device)
            schedule.step()
            if step % 100 == 0 or step == CONFIG['pretrain_steps']:
                metrics=measure(refs,predict(model,synthetic_val,device))
                print('pretrain',step,'loss',loss,'synthetic_validation',metrics,flush=True)
        save_weights(out/'synthetic.pt',model)
        write_json(out/'pretrain-result.json', {'steps':step,'synthetic_validation':metrics,'sha256':sha(out/'synthetic.pt')})
    elif args.action == 'adapt':
        train_rows, train = load_rows(args.train,True)
        val_rows, val = load_rows(args.validation,True)
        if {r['expedition'] for r in train_rows} & {r['expedition'] for r in val_rows}:
            raise ValueError('train and validation expeditions overlap')
        if {r['id'] for r in train_rows} & {r['id'] for r in val_rows}:
            raise ValueError('train and validation IDs overlap')
        synthetic_train = synthetic_set(1024,seed+2,available)
        model=get_weights(out/'synthetic.pt',device)
        optimizer=torch.optim.AdamW(model.parameters(),lr=CONFIG['adapt_lr'])
        history=[]
        baseline=measure(val_rows,predict(model,val,device))
        print('synthetic_on_validation',baseline,flush=True)
        best_key=None
        for step in range(1,CONFIG['adapt_steps']+1):
            real_n=round(CONFIG['batch_size'] * CONFIG['real_fraction'])
            batch=random.choices(train,k=real_n)+random.choices(synthetic_train,k=CONFIG['batch_size']-real_n)
            loss=fit_batch(model,optimizer,batch,device)
            if step % CONFIG['validate_every'] == 0:
                metrics=measure(val_rows,predict(model,val,device))
                history.append({'step':step,'loss':loss,'validation':metrics})
                key=(metrics['exact'],-metrics['cer'])
                if best_key is None or key > best_key:
                    best_key=key
                    selected=step
                    save_weights(out/'adapted.pt',model)
                print('adapt',step,'validation',metrics,'selected',selected,flush=True)
        selected_model=get_weights(out/'adapted.pt', device)
        write_json(out/'freeze.json',{'config':CONFIG,'source_sha256':sha(Path(__file__)),
            'train_manifest_sha256':sha(args.train),'validation_manifest_sha256':sha(args.validation),
            'validation_synthetic':baseline,'validation_adapted':measure(val_rows,predict(selected_model,val,device)),
            'training_adapted':measure(train_rows,predict(selected_model,train,device)),
            'selected_step':selected,'history':history,'checkpoint_sha256':{s:sha(out/(s+'.pt')) for s in ['synthetic','adapted']}})
        print('frozen',sha(out/'freeze.json'),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['pretrain','adapt','predict'])
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--train',type=Path,default=ROOT/'corpus/train.jsonl')
    parser.add_argument('--validation',type=Path,default=ROOT/'corpus/validation.jsonl')
    parser.add_argument('--manifest',type=Path,default=ROOT/'corpus/test.jsonl')
    run(parser.parse_args())
