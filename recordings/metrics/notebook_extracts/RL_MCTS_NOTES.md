# Official RL + MCTS notes (kiyotah sample)

Source: `notebooks/kaggle_pull/official_rl_mcts/`  
Weights: `output/out/model0.pth` … `model4.pth` (~50MB each, PyTorch)

## Usable for our stack

| Asset | Use |
|-------|-----|
| Train / MCTS loop structure | Reference for `train_lucario_field_mcts.py` CUDA path |
| `BATCH_SIZE = 128` | Match local field train batch if memory allows |
| model*.pth | **Not** for Archaludon submission (different deck/obs encoding) |
| device=cuda | Confirmed compatible with 4080 SUPER + torch 2.6 cu124 |

## Do not

- Ship torch models inside `submission.tar.gz` for rule Archaludon
- Replace Archaludon rule pilot with Lucario MCTS weights

## Next integration (when core ≥58%)

1. Keep Arch as rule + R13/R15 levers  
2. Side-train Lucario/Search field MCTS with BATCH 128 + CUDA  
3. Use official 4 + notebooks suite as fixed eval field  
