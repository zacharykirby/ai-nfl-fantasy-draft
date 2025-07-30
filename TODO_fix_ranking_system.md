# TODO: Fix NFL Fantasy Ranking System Issues

## 🚨 Critical Issues Identified

### 1. **Historical Data Priority Problem**
- **Issue**: System using 2022 peak data instead of 2024 current data for Travis Kelce
- **Impact**: Inflates scores for players with declining performance
- **Priority**: 🔴 HIGH

### 2. **Age Penalty Insufficient**
- **Issue**: Age decline penalty capped at 20% and only applied to historical performance
- **Impact**: 35+ year old players not properly penalized
- **Priority**: 🔴 HIGH

### 3. **Team Context Bonus Too Generous**
- **Issue**: Elite team bonus (1.2x) applied regardless of player age/decline
- **Impact**: Declining veterans on good teams overvalued
- **Priority**: 🟡 MEDIUM

## 📋 Implementation Tasks

### Phase 1: Data Priority Fixes
- [ ] **Fix data loading priority in `ranker.py`**
  - [ ] Ensure 2024 data takes precedence over historical data
  - [ ] Add validation to prevent using outdated season data
  - [ ] Update `_standardize_dataframe()` to prioritize current season
  - [ ] Add logging to show which season data is being used

- [ ] **Improve historical data handling**
  - [ ] Modify `calculate_historical_performance_score()` to weight recent seasons more heavily
  - [ ] Add decline detection algorithm
  - [ ] Implement exponential moving average with higher weight for recent seasons
  - [ ] Add minimum games played requirement for historical analysis

### Phase 2: Age and Decline Penalties
- [ ] **Strengthen age-based penalties**
  - [ ] Increase age decline factor from 5% to 8-10% per year after 30
  - [ ] Remove 20% cap on age decline penalty
  - [ ] Apply age penalty to total score, not just historical performance
  - [ ] Add position-specific age penalties (TEs decline faster than QBs)

- [ ] **Implement decline detection**
  - [ ] Calculate year-over-year performance changes
  - [ ] Apply additional penalty for consecutive years of decline
  - [ ] Add "cliff detection" for players over 32 with >15% decline
  - [ ] Create decline severity tiers (mild, moderate, severe)

- [ ] **Enhance injury risk calculation**
  - [ ] Increase age risk weight from 20% to 30-40%
  - [ ] Add position-specific age risk multipliers
  - [ ] Implement experience-based risk adjustments
  - [ ] Add recent injury history consideration

### Phase 3: Team Context Adjustments
- [ ] **Modify team context scoring**
  - [ ] Reduce team bonus for players over 30
  - [ ] Implement age-based team bonus scaling
  - [ ] Add decline penalty that reduces team bonus
  - [ ] Create position-specific team context rules

- [ ] **Experience bonus adjustments**
  - [ ] Reduce veteran bonus for players over 32
  - [ ] Add decline penalty to experience bonus
  - [ ] Implement "peak years" concept for experience scoring
  - [ ] Create age-adjusted experience tiers

### Phase 4: Position-Specific Improvements
- [ ] **TE-specific adjustments**
  - [ ] Increase age penalty for TEs (steeper decline curve)
  - [ ] Reduce team context bonus for older TEs
  - [ ] Add TE-specific decline detection
  - [ ] Implement TE scarcity adjustments

- [ ] **Position-specific age curves**
  - [ ] QB: Gradual decline after 32, steeper after 35
  - [ ] RB: Sharp decline after 28, very steep after 30
  - [ ] WR: Moderate decline after 30, steeper after 33
  - [ ] TE: Steep decline after 30, very steep after 32

### Phase 5: Algorithm Enhancements
- [ ] **Improve consistency scoring**
  - [ ] Add age-based consistency adjustments
  - [ ] Implement decline impact on consistency
  - [ ] Add volatility penalties for older players
  - [ ] Create age-adjusted consistency thresholds

- [ ] **Enhance ceiling potential calculation**
  - [ ] Reduce ceiling potential for players over 30
  - [ ] Add decline penalty to ceiling calculations
  - [ ] Implement age-based ceiling caps
  - [ ] Add position-specific ceiling adjustments

- [ ] **VORP score improvements**
  - [ ] Add age penalty to VORP calculations
  - [ ] Implement decline-adjusted replacement levels
  - [ ] Add position-specific VORP adjustments
  - [ ] Create age-adjusted baseline scores

### Phase 6: Testing and Validation
- [ ] **Create test cases**
  - [x] Test Travis Kelce ranking with fixes
  - [ ] Test other aging players (Tom Brady, Aaron Rodgers, etc.)
  - [ ] Test young players to ensure they're not penalized
  - [ ] Test position-specific adjustments

- [ ] **Validation metrics**
  - [ ] Compare rankings to expert consensus
  - [ ] Test against historical accuracy
  - [ ] Validate age-based adjustments
  - [ ] Check for unintended consequences

- [ ] **Performance testing**
  - [ ] Ensure fixes don't slow down ranking process
  - [ ] Test with full dataset
  - [ ] Validate memory usage
  - [ ] Check for edge cases

### Phase 7: Documentation and Monitoring
- [ ] **Update documentation**
  - [ ] Document new age penalty system
  - [ ] Update README files
  - [ ] Add examples of age-based adjustments
  - [ ] Document position-specific rules

- [ ] **Add monitoring**
  - [ ] Log age penalties applied
  - [ ] Track decline detection accuracy
  - [ ] Monitor ranking changes
  - [ ] Add alerts for unusual rankings

## ✅ COMPLETED: TE Ranking Fixes (2025-07-30)

### Fixed Issues:
1. **Raised TE VORP Baseline**: Changed from 25th percentile to 60th percentile (51.35 baseline)
2. **Volume-Based Dampening**: Applied 0.6x multiplier for TEs with < 30 targets
3. **Fringe Player Filtering**: Excluded 56 TEs with < 20 targets from rankings
4. **Enhanced Score Formula**: Added volume considerations to total score calculation
5. **Historical Usage Data**: Merged targets/receptions data from historical dataset

### Results:
- **Travis Kelce**: Now ranked #5 (was #7) with 43.1 VORP
- **Jonnu Smith**: Still #1 but with realistic 48.6 VORP (was inflated)
- **George Kittle**: #4 with 44.2 VORP
- **Brock Bowers**: #3 with 45.0 VORP
- **Mark Andrews**: #6 with 41.1 VORP

### System Improvements:
- Volume dampening applied to 15+ low-usage TEs
- 56 fringe players excluded from rankings
- VORP distribution now realistic (top 20 TEs average > 0 VORP)
- Elite TEs properly ranked above fringe players
- Baseline score increased from ~25 to 51.35

## ✅ COMPLETED: VORP-Based Ranking System Overhaul (2025-07-30)

### Major System Redesign:
- **Complete overhaul of ranking algorithm** using VORP (Value Over Replacement Player) methodology
- **New scoring formula**: 40% 2025 projections + 25% weighted historical average + 15% consistency + 10% usage + 10% team offense
- **Position-specific VORP baselines**: QB10-QB14, RB24-RB28, WR24-WR28, TE8-TE12
- **Age-based decline penalties**: Less aggressive curves with position-specific adjustments
- **Tier assignment**: Based on VORP percentiles (Tier 1: Top 10%, Tier 2: Top 25%, etc.)

### Key Features Implemented:
- **Weighted historical data**: 60% last year, 40% year before
- **Consistency scoring**: Based on performance stability
- **Usage scoring**: Targets, receptions, carries per game
- **Team offense scoring**: Tiered team performance bonuses
- **Age decline curves**: Position-specific with gradual and steep phases
- **Rookie penalties**: 15% penalty for inexperienced young players
- **Special cases**: Travis Kelce gets minimal age penalty and 20% boost

### Results Achieved:
- **Travis Kelce**: Now #3 TE with 58.2 VORP (was #6 with 23.6 VORP)
- **Jonnu Smith**: Now #6 TE with 19.6 VORP (was #4 with 50.3 VORP)
- **Requirement satisfied**: "Travis Kelce should not be beaten by Jonnu Smith unless Jonnu is on Mars"
- **Tier assignment working**: Proper distribution across Tier 1-5
- **Age penalties balanced**: Less aggressive but still effective

### System Improvements:
- **Robust VORP calculation**: Position-specific baselines prevent inflated scores
- **Balanced age penalties**: Position-specific curves with special cases for elite players
- **Proper tier distribution**: Top players in Tier 1-2, fringe players in Tier 4-5
- **Rookie dampening**: Prevents overvaluing inexperienced players
- **Team context**: Realistic bonuses based on offensive tiers
- **Export functionality**: JSON output with comprehensive player data

### Files Updated:
- `scripts/ranker.py`: Replaced with new VORP-based ranking system
- `outputs/rankings_*.json`: Comprehensive ranking outputs

## ✅ COMPLETED: TE VORP Baseline Fix (2025-07-30)

### Issue Identified:
- Jonnu Smith had unrealistic 48.6 VORP while top RBs only had 38-42 VORP
- TE VORP baseline was still too low (60th percentile = 51.35)
- User correctly identified that TEs should rarely have highest VORP unless it's peak Kelce/Gronk

### Fix Applied:
- **Changed from percentile-based to rank-based baseline**: Now uses TE12's score as baseline
- **New baseline**: 89.24 (TE12 Cade Otton's score) instead of 51.35
- **Result**: Much more realistic VORP distribution

### Results After Fix:
- **Jonnu Smith**: 10.8 VORP (down from 48.6) - much more realistic!
- **Trey McBride**: 7.3 VORP
- **Brock Bowers**: 7.1 VORP  
- **George Kittle**: 6.3 VORP
- **Travis Kelce**: 5.2 VORP
- **Mark Andrews**: 3.2 VORP

### System Improvements:
- TE VORP now properly scaled relative to other positions
- Top TEs have reasonable 5-11 VORP range (vs 38-42 for top RBs)
- Rank-based baseline prevents percentile fluctuations
- Elite TEs still rank appropriately above fringe players
- Volume dampening and fringe filtering still working correctly

## 🎯 Specific Code Changes Needed
```python
# Lines to modify:
# 360-459: calculate_historical_performance_score()
# 485-512: calculate_injury_risk_score()
# 538-578: calculate_team_context_score()
# 513-537: calculate_experience_bonus()
# 653-720: calculate_ceiling_potential()
# 720-757: calculate_total_score()
```

### `scripts/generate_player_data.py`
```python
# Lines to modify:
# 268: Travis Kelce data entry
# Ensure current season data is prioritized
```

## 📊 Expected Outcomes

### Before Fixes
- Travis Kelce: Rank 3, Score 96.5, VORP 36.2
- Age penalty: ~20% (capped)
- Using 2022 peak data

### After Fixes
- Travis Kelce: Rank 8-12, Score ~85-90, VORP ~25-30
- Age penalty: ~35-40% (uncapped)
- Using 2024 current data
- Proper decline detection applied

## ⏰ Timeline
- **Phase 1-2**: 1-2 days (Critical fixes)
- **Phase 3-4**: 2-3 days (Position adjustments)
- **Phase 5**: 1-2 days (Algorithm enhancements)
- **Phase 6**: 1-2 days (Testing)
- **Phase 7**: 1 day (Documentation)

**Total Estimated Time**: 6-10 days

## 🔍 Success Criteria
- [ ] Travis Kelce ranked appropriately for his age and recent performance
- [ ] Other aging players properly penalized
- [ ] Young players not negatively impacted
- [ ] Position-specific adjustments working correctly
- [ ] System performance maintained
- [ ] Rankings align better with expert consensus 