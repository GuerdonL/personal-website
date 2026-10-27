"""BiLSTM-CTC recognizer over ink features. ~2 M parameters.

    python model.py          # prints parameter count and a forward-pass shape check
"""
import torch, torch.nn as nn
from features import N_FEATURES

# output alphabet: index 0 is the CTC blank. Symbols get their own tokens (phase 5 adds more).
CHARS = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
SYMBOLS = ['→', '←', '↑', '↓', '•', '□', '✓', '✗', '°', '€', '£', '—', '…', '“', '”', '‘', '’']
VOCAB = ['<blank>'] + list(CHARS) + SYMBOLS
CHAR2ID = {c: i for i, c in enumerate(VOCAB)}

def encode(text):
    return [CHAR2ID[c] for c in text if c in CHAR2ID]

def decode_greedy(ids):
    out, prev = [], 0
    for i in ids:
        if i != prev and i != 0: out.append(VOCAB[i])
        prev = i
    return ''.join(out)

class InkRecognizer(nn.Module):
    def __init__(self, n_feat=N_FEATURES, hidden=192, layers=2, n_out=len(VOCAB), dropout=0.2):
        super().__init__()
        self.inp = nn.Sequential(nn.Linear(n_feat, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
        self.rnn = nn.LSTM(hidden, hidden, num_layers=layers, bidirectional=True, batch_first=True, dropout=dropout)
        self.out = nn.Linear(2 * hidden, n_out)
    def forward(self, x, lengths=None):
        """x [B, T, F] → log-probs [B, T, V]"""
        h = self.inp(x)
        if lengths is not None:
            h = nn.utils.rnn.pack_padded_sequence(h, lengths.cpu(), batch_first=True, enforce_sorted=False)
            h, _ = self.rnn(h)
            h, _ = nn.utils.rnn.pad_packed_sequence(h, batch_first=True, total_length=x.shape[1])
        else:
            h, _ = self.rnn(h)
        return self.out(h).log_softmax(-1)

if __name__ == '__main__':
    m = InkRecognizer()
    print('params', sum(p.numel() for p in m.parameters()) / 1e6, 'M; vocab', len(VOCAB))
    y = m(torch.randn(2, 50, N_FEATURES), torch.tensor([50, 30]))
    print('out', tuple(y.shape))
