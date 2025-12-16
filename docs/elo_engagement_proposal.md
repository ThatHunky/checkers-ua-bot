# Dynamic ELO System Proposal: More Engaging Rating Experience

## Executive Summary

This proposal outlines changes to make the ELO rating system more engaging and exciting, especially for new players. By starting with a lower initial rating and implementing dynamic K-factor adjustments based on experience, players will see more dramatic rating changes early on, creating a more rewarding progression experience.

---

## Current System Issues

### Problems with Current Implementation
- **High starting rating (1200)**: New players start in the middle of the pack, making early progression feel slow
- **Fixed K-factor (32)**: All players experience the same rating volatility regardless of experience
- **Slow initial progression**: New players need many games to see meaningful rating changes
- **Lack of excitement**: Rating changes feel predictable and unexciting

### Impact on Player Engagement
- New players may feel discouraged by slow progress
- No sense of "climbing" from the bottom
- Rating changes don't feel impactful
- Less motivation to play more games

---

## Proposed Solution: Dynamic ELO System

### Core Changes

1. **Lower Initial Rating**: Start new players at 800 instead of 1200
2. **Dynamic K-Factor**: Adjust rating volatility based on number of games played
3. **Provisional Rating Period**: Special handling for first 10-20 games
4. **Accelerated Early Progression**: Larger swings help players find their true skill level faster

---

## Detailed Proposal

### 1. Lower Initial Rating

#### New Starting Rating: **800 ELO**

**Rationale:**
- Creates a clear "bottom" to climb from
- Makes early wins feel more impactful
- Provides more room for progression
- Aligns with rank system (Новачок starts at 0-999)

**Impact on Rank System:**
- New players start as **Новачок** (0-999 range)
- First win likely moves them to **Шашкар** (1000-1099)
- Creates immediate sense of achievement

**Migration Strategy:**
- Existing players keep their current rating
- Only new players start at 800
- Consider optional "reset" for existing players who want fresh start

---

### 2. Dynamic K-Factor System

#### K-Factor Based on Games Played

The K-factor determines how much a player's rating can change per game. Higher K-factor = more volatile ratings.

| Games Played | K-Factor | Description | Example Change* |
|--------------|----------|-------------|-----------------|
| 0-5 | **64** | Provisional - Very volatile | ±32 to ±48 |
| 6-10 | **48** | Still finding skill level | ±24 to ±36 |
| 11-20 | **40** | Settling in | ±20 to ±30 |
| 21-30 | **36** | Becoming established | ±18 to ±27 |
| 31-50 | **32** | Standard volatility | ±16 to ±24 |
| 51-100 | **28** | Experienced player | ±14 to ±21 |
| 101+ | **24** | Veteran - Stable rating | ±12 to ±18 |

*Example changes assume equal-rated opponents. Actual changes vary based on rating difference.

#### Formula for Dynamic K-Factor

```python
def get_k_factor(games_played: int) -> int:
    """Calculate K-factor based on number of games played."""
    if games_played <= 5:
        return 64  # Very volatile for new players
    elif games_played <= 10:
        return 48
    elif games_played <= 20:
        return 40
    elif games_played <= 30:
        return 36
    elif games_played <= 50:
        return 32  # Current standard
    elif games_played <= 100:
        return 28
    else:
        return 24  # Stable for veterans
```

#### Benefits
- **New players**: See dramatic rating changes, making each game feel impactful
- **Experienced players**: More stable ratings prevent wild swings
- **Natural progression**: System automatically adjusts as players gain experience
- **Faster skill discovery**: New players find their true skill level in fewer games

---

### 3. Provisional Rating Period

#### First 10 Games: "Provisional" Status

During the first 10 games, players are in a "provisional" period with special characteristics:

**Features:**
- Higher K-factor (64 for first 5, 48 for next 5)
- Visual indicator: "🆕 Provisional" badge in profile
- Special messaging: "You're still establishing your rating!"
- Faster matchmaking: Wider rating range for provisional players

**Display:**
```
📊 Профіль гравця: Новачок

🆕 Provisional Rating
⭐ Рейтинг: 945 (🆕 встановлюється)
🎮 Ігор: 3/10 (до стабільного рейтингу)
```

**After 10 Games:**
- Rating becomes "established"
- K-factor drops to standard progression
- Player gets full rank display
- Normal matchmaking restrictions apply

---

### 4. Enhanced Rating Change Display

#### More Exciting Visual Feedback

**For New Players (0-20 games):**
```
🏆 Перемога!

Роман Відлюдник виграв партію!

📊 Рейтинг:
🆕 Provisional | Роман Відлюдник: 945 → 1,012 (+67) 🔥
   ⚡ Великий стрибок! Ви вже Шашкар! 🎯

Vsevolod: 1,082 → 1,015 (-67)
```

**For Established Players (21+ games):**
```
🏆 Перемога!

Роман Відлюдник виграв партію!

📊 Рейтинг:
🏅 Гравець 🎮 Роман Відлюдник: 1,245 → 1,261 (+16)
   📈 Стабільний прогрес

Vsevolod: 1,230 → 1,214 (-16)
```

#### Special Messages for Big Changes
- **+50 or more**: "🚀 МАСИВНИЙ СТРИБОК!"
- **+30 to +49**: "⚡ Великий прогрес!"
- **+20 to +29**: "📈 Гарний результат!"
- **Rank up**: "🎉 ВИ ДОСЯГЛИ НОВОГО РАНГУ!"

---

## Implementation Details

### Database Changes

No schema changes required! We can use existing `games_played` field.

### Code Changes

#### 1. Update Constants

```python
# ratings.py

# New initial rating
INITIAL_RATING = 800  # Changed from 1200

# Base K-factor (used as fallback)
BASE_K_FACTOR = 32

def get_k_factor(games_played: int) -> int:
    """Get dynamic K-factor based on games played."""
    if games_played <= 5:
        return 64
    elif games_played <= 10:
        return 48
    elif games_played <= 20:
        return 40
    elif games_played <= 30:
        return 36
    elif games_played <= 50:
        return 32
    elif games_played <= 100:
        return 28
    else:
        return 24
```

#### 2. Update `calculate_elo_change` Method

```python
@staticmethod
def calculate_elo_change(
    winner_rating: int,
    loser_rating: int,
    winner_games: int = 0,
    loser_games: int = 0,
    k_factor: Optional[int] = None
) -> tuple[int, int]:
    """
    Calculate ELO rating changes with dynamic K-factor.
    
    Args:
        winner_rating: Current rating of winner
        loser_rating: Current rating of loser
        winner_games: Number of games winner has played
        loser_games: Number of games loser has played
        k_factor: Optional fixed K-factor (uses dynamic if None)
    """
    # Use dynamic K-factor for each player
    winner_k = k_factor if k_factor else get_k_factor(winner_games)
    loser_k = k_factor if k_factor else get_k_factor(loser_games)
    
    # Calculate expected scores
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner
    
    # Calculate changes with individual K-factors
    # Use average K-factor to maintain zero-sum property
    avg_k = (winner_k + loser_k) / 2
    
    winner_change = round(avg_k * (1.0 - expected_winner))
    loser_change = -winner_change  # Zero-sum
    
    new_winner_rating = winner_rating + winner_change
    new_loser_rating = loser_rating + loser_change
    
    return new_winner_rating, new_loser_rating
```

#### 3. Update `record_game` Method

```python
async def record_game(
    self,
    winner_id: int,
    winner_name: str,
    loser_id: int,
    loser_name: str
) -> Tuple[dict, dict]:
    """Record game with dynamic K-factor."""
    # Get current ratings and game counts
    winner = await self.get_player(winner_id, winner_name)
    loser = await self.get_player(loser_id, loser_name)
    
    winner_games = winner.get("games_played", 0)
    loser_games = loser.get("games_played", 0)
    
    # Calculate new ratings with dynamic K-factor
    new_winner_rating, new_loser_rating = self.calculate_elo_change(
        winner["rating"],
        loser["rating"],
        winner_games,
        loser_games
    )
    
    # Rest of implementation remains the same...
```

---

## Expected Impact

### Player Experience Improvements

#### New Players (0-10 games)
- **Before**: Start at 1200, win = +16, feels slow
- **After**: Start at 800, win = +40-60, feels exciting!
- **Result**: Immediate sense of progression, more motivation to play

#### Early Players (11-30 games)
- **Before**: Fixed +16-24 changes
- **After**: +20-30 changes, still exciting
- **Result**: Continued engagement, faster skill discovery

#### Experienced Players (50+ games)
- **Before**: Fixed +16-24 changes
- **After**: +12-18 changes, more stable
- **Result**: Ratings feel more accurate, less frustrating swings

### Engagement Metrics (Expected)

- **New player retention**: +25-40% (more exciting early experience)
- **Games per new player**: +30-50% (faster progression = more motivation)
- **Time to first rank-up**: -60% (from ~5 games to ~2 games)
- **Player satisfaction**: Higher (more visible progress)

---

## Rank System Alignment

### Updated Rank Thresholds

With new 800 starting rating, ranks remain the same but progression feels better:

| Rank | ELO Range | Starting Distance | Games to Reach* |
|------|-----------|------------------|-----------------|
| **Новачок** | 0-999 | 0-199 | Start here |
| **Шашкар** | 1000-1099 | 200-299 | 2-4 games |
| **Учень** | 1100-1199 | 300-399 | 4-6 games |
| **Гравець** | 1200-1299 | 400-499 | 6-8 games |
| **Майстер** | 1300-1399 | 500-599 | 8-12 games |

*Assuming 50% win rate with similar-rated opponents

### Progression Feel

**Old System (1200 start):**
- Game 1: 1200 → 1216 (+16) - "Meh, barely moved"
- Game 5: ~1220 - "Still feels the same"
- Game 10: ~1240 - "Finally seeing progress"

**New System (800 start):**
- Game 1: 800 → 860 (+60) - "Wow, big jump!"
- Game 2: 860 → 920 (+60) - "Almost Шашкар!"
- Game 3: 920 → 1010 (+90) - "🎉 Rank up to Шашкар!"
- Game 5: ~1100 - "Already Учень!"
- Game 10: ~1200 - "Established as Гравець!"

---

## Migration Strategy

### For Existing Players

**Option 1: Keep Current Ratings (Recommended)**
- Existing players keep their current rating
- Only new players start at 800
- Dynamic K-factor applies to all players based on games played
- **Pros**: No disruption, fair to existing players
- **Cons**: Two-tier system temporarily

**Option 2: Soft Reset**
- All players below 1200: Keep rating
- All players 1200+: Subtract 400 (1200 → 800, 1500 → 1100)
- **Pros**: Unified starting point
- **Cons**: May frustrate existing players

**Option 3: Optional Reset**
- Add command `/resetrating` for players who want fresh start
- Resets to 800, clears stats
- **Pros**: Player choice
- **Cons**: Some may abuse it

**Recommendation**: Option 1 (keep current ratings, apply dynamic K-factor to all)

---

## Edge Cases & Considerations

### 1. Rating Floor Protection

**Issue**: New players could drop below 0 with large losses

**Solution**: Implement soft floor at 400 ELO
- Players can't drop below 400
- Still show actual calculated rating internally
- Display as "400+" if below floor

### 2. Matchmaking with Lower Starting Rating

**Issue**: New players at 800 may have trouble finding matches

**Solution**: 
- Provisional players (0-10 games) have wider matchmaking range (±200 instead of ±50)
- After 10 games, normal matchmaking applies
- Matchmaking already handles this with expanding range

### 3. Leaderboard Impact

**Issue**: Lower starting rating might skew leaderboard

**Solution**:
- Leaderboard remains sorted by rating (highest first)
- New players will naturally rise if they're skilled
- Unskilled new players stay low (as intended)
- No negative impact on leaderboard integrity

### 4. K-Factor Calculation for Both Players

**Issue**: Different K-factors for winner/loser could break zero-sum

**Solution**: Use average K-factor
- `avg_k = (winner_k + loser_k) / 2`
- Apply same K-factor to both players
- Maintains zero-sum property
- Still reflects experience level

---

## Testing Plan

### Test Scenarios

1. **New Player Journey**
   - Start at 800
   - Play 10 games with 50% win rate
   - Verify rating progression
   - Check K-factor decreases appropriately

2. **Provisional Period**
   - Play first 5 games (K=64)
   - Play next 5 games (K=48)
   - Verify rating stabilizes after 10 games

3. **Mixed Experience Match**
   - New player (5 games, K=64) vs Veteran (150 games, K=24)
   - Verify average K-factor used
   - Verify zero-sum maintained

4. **Rank Progression**
   - Track time to reach each rank
   - Verify feels faster than before
   - Check rank-up notifications work

5. **Edge Cases**
   - Player with 0 games (should use K=64)
   - Player with exactly 10 games (should use K=48)
   - Very high-rated new player (should still have high K)

---

## Rollout Plan

### Phase 1: Implementation (Week 1)
1. Update `INITIAL_RATING` constant to 800
2. Implement `get_k_factor()` function
3. Update `calculate_elo_change()` to accept games_played
4. Update `record_game()` to pass games_played
5. Add provisional status detection

### Phase 2: UI Updates (Week 1-2)
1. Update rating display messages
2. Add provisional badge/indicator
3. Add special messages for big rating changes
4. Update rank-up notifications

### Phase 3: Testing (Week 2)
1. Internal testing with test accounts
2. Beta testing with select players
3. Monitor rating distributions
4. Adjust K-factor thresholds if needed

### Phase 4: Launch (Week 3)
1. Deploy to production
2. Monitor metrics (retention, games played)
3. Collect player feedback
4. Make adjustments based on data

---

## Success Metrics

### Key Performance Indicators

1. **New Player Engagement**
   - Average games played in first week: Target +40%
   - Retention rate (day 7): Target +25%
   - Time to first rank-up: Target -60%

2. **Rating Distribution**
   - More players in lower ranks (expected)
   - Smoother distribution curve
   - Fewer players stuck at starting rating

3. **Player Satisfaction**
   - Positive feedback on rating changes
   - Reduced complaints about slow progression
   - Increased leaderboard participation

4. **System Health**
   - Rating accuracy (players find true skill level faster)
   - Matchmaking quality (still finding good matches)
   - No rating inflation/deflation issues

---

## Future Enhancements

### Potential Additions

1. **Bonus Rating for Streaks**
   - Small bonus (+2-5) for maintaining win streaks
   - Encourages continued play

2. **Rating Decay for Inactivity**
   - Players inactive 30+ days lose 10-20 rating
   - Keeps leaderboard active

3. **Seasonal Soft Resets**
   - Every 3 months, all ratings reduced by 10%
   - Creates fresh competition

4. **Placement Matches**
   - First 5 games are "placement matches"
   - Larger rating swings to find initial skill
   - Special UI during placement

---

## Conclusion

This dynamic ELO system creates a more engaging experience by:

1. **Starting lower (800)**: Creates clear progression path
2. **Dynamic K-factor**: Exciting changes for new players, stability for veterans
3. **Provisional period**: Special handling for new players
4. **Better feedback**: More exciting rating change messages

The system maintains mathematical integrity while dramatically improving player engagement, especially for new players. The implementation is straightforward and requires minimal database changes.

---

## Questions for Discussion

1. **Starting Rating**: Is 800 appropriate, or should it be 700 or 900?

2. **K-Factor Thresholds**: Are the games-played breakpoints (5, 10, 20, etc.) appropriate?

3. **Migration**: Should existing players keep ratings or get soft reset?

4. **Provisional Period**: Should it be 10 games or 20 games?

5. **Rating Floor**: Should we implement 400 floor, or allow ratings to go lower?

---

*Document Version: 1.0*  
*Last Updated: 2025-01-XX*  
*Author: AI Assistant*

