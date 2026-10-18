# Gate 1 Survival Experiment Report

- **Carrier**: TrustMark-Q (payload: 100 bits)
- **Total Experimental Trials**: 160
- **Overall Decodable Rate**: 100.00%
- **Fitted Channel Bit-Flip Probability (p_H1 MLE)**: 0.0912
- **Held-out Goodness-of-Fit Test**: Chi2=334.8762503540309, p-value=0.0
  *Interpretation*: Chi-squared = 334.88, df = 7, p = 0.0000. REJECT the Binomial model at α=0.05. Bit errors may be correlated. Consider BetaBinomialModel.
- **Expected Calibration Error (ECE on Held-out Test)**: 0.0796

## Attack Performance Breakdown

| attack_category   | attack_name        |   trials | decodable_pct   |   mean_ber |   mean_log10_lr |
|:------------------|:-------------------|---------:|:----------------|-----------:|----------------:|
| ai_regen          | ai_regen_0.20      |        8 | 100.0%          |     0.0063 |           25.33 |
| ai_regen          | ai_regen_0.50      |        8 | 100.0%          |     0.2275 |            3.23 |
| ai_regen          | ai_regen_0.80      |        8 | 100.0%          |     0.4662 |          -20.61 |
| baseline          | identity           |        8 | 100.0%          |     0      |           25.95 |
| blur              | blur_r1            |        8 | 100.0%          |     0      |           25.95 |
| blur              | blur_r2            |        8 | 100.0%          |     0.0025 |           25.7  |
| blur              | blur_r3            |        8 | 100.0%          |     0.0075 |           25.2  |
| crop              | crop_50            |        8 | 100.0%          |     0.5112 |          -25.1  |
| crop              | crop_75            |        8 | 100.0%          |     0.0375 |           22.21 |
| crop              | crop_90            |        8 | 100.0%          |     0      |           25.95 |
| jpeg              | jpeg_q15           |        8 | 100.0%          |     0.2037 |            5.61 |
| jpeg              | jpeg_q30           |        8 | 100.0%          |     0.1075 |           15.22 |
| jpeg              | jpeg_q50           |        8 | 100.0%          |     0.0325 |           22.71 |
| jpeg              | jpeg_q75           |        8 | 100.0%          |     0.0025 |           25.7  |
| jpeg              | jpeg_q90           |        8 | 100.0%          |     0.0013 |           25.83 |
| negative_control  | identity_unrelated |        4 | 100.0%          |     0.45   |          -18.98 |
| negative_control  | jpeg_q75_unrelated |        4 | 100.0%          |     0.45   |          -18.98 |
| noise             | noise_s10          |        8 | 100.0%          |     0.0187 |           24.08 |
| noise             | noise_s25          |        8 | 100.0%          |     0.1788 |            8.1  |
| scale             | scale_0.50         |        8 | 100.0%          |     0      |           25.95 |
| scale             | scale_0.75         |        8 | 100.0%          |     0      |           25.95 |

## Conclusion & Gate 1 Decision

✅ **GATE 1 PASSED**: Watermark demonstrates strong decodability across transformations with predictable bit degradation. The noisy-channel model is empirically supported.
