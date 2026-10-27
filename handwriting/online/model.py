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

SUBSAMPLE = 4   # the conv front-end shortens time by this factor; lengths passed to CTC must be divided the same way

class InkRecognizer(nn.Module):
    """conv front-end (time ÷ 4) → BiLSTM → per-frame character log-probs (CTC)."""
    def __init__(self, n_feat=N_FEATURES, hidden=192, layers=2, n_out=len(VOCAB), dropout=0.2):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(n_feat, hidden, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv1d(hidden, hidden, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv1d(hidden, hidden, 3, stride=1, padding=1), nn.ReLU())
        self.rnn = nn.LSTM(hidden, hidden, num_layers=layers, bidirectional=True, batch_first=True, dropout=dropout)
        self.out = nn.Linear(2 * hidden, n_out)
    @staticmethod
    def out_lengths(lengths): return (lengths + SUBSAMPLE - 1) // SUBSAMPLE
    def forward(self, x, lengths=None):
        """x [B, T, F] → log-probs [B, ceil(T/4), V]"""
        h = self.conv(x.transpose(1, 2)).transpose(1, 2)
        if lengths is not None:
            ol = self.out_lengths(lengths).clamp(max=h.shape[1])
            h = nn.utils.rnn.pack_padded_sequence(h, ol.cpu(), batch_first=True, enforce_sorted=False)
            h, _ = self.rnn(h)
            h, _ = nn.utils.rnn.pad_packed_sequence(h, batch_first=True)
        else:
            h, _ = self.rnn(h)
        return self.out(h).log_softmax(-1)

if __name__ == '__main__':
    m = InkRecognizer()
    print('params', sum(p.numel() for p in m.parameters()) / 1e6, 'M; vocab', len(VOCAB))
    y = m(torch.randn(2, 50, N_FEATURES), torch.tensor([50, 30]))
    print('out', tuple(y.shape), '(time 50 → 13)')
