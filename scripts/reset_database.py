#!/usr/bin/env python3
"""
Database Reset Script for Rating System Overhaul

WARNING: This script will DELETE all existing player data!
Use only when implementing the new rating system.

Usage:
    python scripts/reset_database.py [--confirm]
"""

import asyncio
import aiosqlite
import argparse
import sys
from pathlib import Path

# Database paths - use environment variables or defaults
import os
RATINGS_DB = Path(os.getenv("DB_PATH", "/data/ratings.db"))
GAMEDATA_DB = Path(os.getenv("GAMEDATA_DB_PATH", "/data/gamedata.db"))

# Allow override for testing
if len(sys.argv) > 1 and sys.argv[1] == "--test":
    RATINGS_DB = Path("./test_ratings.db")
    GAMEDATA_DB = Path("./test_gamedata.db")

async def backup_database(db_path: Path):
    """Create backup of database before reset."""
    if not db_path.exists():
        print(f"Database {db_path} does not exist, skipping backup")
        return None
    
    import time
    backup_path = db_path.with_suffix(f".backup.{int(time.time())}.db")
    
    async with aiosqlite.connect(str(db_path)) as source:
        async with aiosqlite.connect(str(backup_path)) as backup:
            await source.backup(backup)
    
    print(f"✓ Backup created: {backup_path}")
    return backup_path

async def reset_ratings_database():
    """Reset and recreate ratings database with new schema."""
    print("Resetting ratings database...")
    
    # Backup existing database
    if RATINGS_DB.exists():
        await backup_database(RATINGS_DB)
        RATINGS_DB.unlink()  # Delete old database
        print(f"✓ Deleted old database: {RATINGS_DB}")
    
    # Create directory if it doesn't exist
    RATINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    
    # Create new database with updated schema
    async with aiosqlite.connect(str(RATINGS_DB)) as db:
        # Core players table with all new fields
        await db.execute("""
            CREATE TABLE players (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                rating INTEGER DEFAULT 800,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                
                -- Streak fields
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                
                -- Statistics fields
                best_rating INTEGER DEFAULT 800,
                peak_rank TEXT,
                total_rating_gained INTEGER DEFAULT 0,
                total_rating_lost INTEGER DEFAULT 0,
                perfect_games INTEGER DEFAULT 0,
                comeback_wins INTEGER DEFAULT 0,
                fastest_win INTEGER,
                longest_game INTEGER,
                games_this_week INTEGER DEFAULT 0,
                games_this_month INTEGER DEFAULT 0,
                last_game_date DATE,
                
                -- Seasonal fields
                season_rating INTEGER DEFAULT 800,
                season_games INTEGER DEFAULT 0,
                
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Achievements table
        await db.execute("""
            CREATE TABLE achievements (
                achievement_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_uk TEXT NOT NULL,
                description TEXT,
                description_uk TEXT,
                icon TEXT,
                category TEXT,
                requirement_value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Player achievements table
        await db.execute("""
            CREATE TABLE player_achievements (
                user_id INTEGER,
                achievement_id TEXT,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                progress INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, achievement_id)
            )
        """)
        
        # Match history table (optional, for analytics)
        await db.execute("""
            CREATE TABLE match_history (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER,
                player2_id INTEGER,
                winner_id INTEGER,
                player1_rating_before INTEGER,
                player1_rating_after INTEGER,
                player2_rating_before INTEGER,
                player2_rating_after INTEGER,
                move_count INTEGER,
                game_duration INTEGER,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance
        await db.execute("CREATE INDEX idx_players_rating ON players(rating)")
        await db.execute("CREATE INDEX idx_players_games ON players(games_played)")
        await db.execute("CREATE INDEX idx_player_achievements_user ON player_achievements(user_id)")
        await db.execute("CREATE INDEX idx_match_history_winner ON match_history(winner_id)")
        await db.execute("CREATE INDEX idx_match_history_played_at ON match_history(played_at)")
        
        await db.commit()
    
    print("✓ Ratings database reset and schema created")

async def populate_achievements():
    """Populate achievements table with all achievements."""
    print("Populating achievements...")
    
    # Complete achievements list (87+ achievements)
    achievements = [
        # Milestone Achievements (12)
        ("first_steps", "First Steps", "Перші Кроки", "Play your first game", "Зіграйте свою першу гру", "🌱", "milestone", 1),
        ("first_victory", "First Victory", "Перша Перемога", "Win your first game", "Виграйте свою першу гру", "🏆", "milestone", 1),
        ("player_10", "Player", "Гравець", "Play 10 games", "Зіграйте 10 ігор", "🎮", "milestone", 10),
        ("statistician", "Statistician", "Статистик", "Play 25 games", "Зіграйте 25 ігор", "📊", "milestone", 25),
        ("centurion", "Centurion", "Сотник", "Play 100 games", "Зіграйте 100 ігор", "💯", "milestone", 100),
        ("veteran_games", "Veteran", "Ветеран", "Play 500 games", "Зіграйте 500 ігор", "🎖️", "milestone", 500),
        ("legend_games", "Legend", "Легенда", "Play 1,000 games", "Зіграйте 1,000 ігор", "👑", "milestone", 1000),
        ("tireless", "Tireless", "Невтомний", "Play 2,500 games", "Зіграйте 2,500 ігор", "🏅", "milestone", 2500),
        ("fast_start", "Fast Start", "Швидкий Старт", "Win 5 games in first 10", "Виграйте 5 ігор з перших 10", "⚡", "milestone", 5),
        ("rising_star", "Rising Star", "Висхідна Зірка", "Gain 200 rating in a week", "Отримайте 200 рейтингу за тиждень", "📈", "milestone", 200),
        ("meteor", "Meteor", "Метеор", "Gain 300 rating in a week", "Отримайте 300 рейтингу за тиждень", "🚀", "milestone", 300),
        ("comet", "Comet", "Комета", "Gain 500 rating in a month", "Отримайте 500 рейтингу за місяць", "💫", "milestone", 500),
        
        # Rank Achievements (13)
        ("rank_shashkar", "Шашкар", "Шашкар", "Reach Шашкар rank", "Досягніть рангу Шашкар", "🎯", "rank", 1000),
        ("rank_uchen", "Учень", "Учень", "Reach Учень rank", "Досягніть рангу Учень", "📚", "rank", 1100),
        ("rank_gravec", "Гравець", "Гравець", "Reach Гравець rank", "Досягніть рангу Гравець", "🎮", "rank", 1200),
        ("rank_maister", "Майстер", "Майстер", "Reach Майстер rank", "Досягніть рангу Майстер", "⚔️", "rank", 1300),
        ("rank_veteran", "Ветеран", "Ветеран", "Reach Ветеран rank", "Досягніть рангу Ветеран", "🛡️", "rank", 1400),
        ("rank_chempion", "Чемпіон", "Чемпіон", "Reach Чемпіон rank", "Досягніть рангу Чемпіон", "🏆", "rank", 1500),
        ("rank_kozak", "Козак", "Козак", "Reach Козак rank", "Досягніть рангу Козак", "⚡", "rank", 1600),
        ("rank_getman", "Гетьман", "Гетьман", "Reach Гетьман rank", "Досягніть рангу Гетьман", "👑", "rank", 1700),
        ("rank_bogatyr", "Богатир", "Богатир", "Reach Богатир rank", "Досягніть рангу Богатир", "⚔️", "rank", 1800),
        ("rank_knyaz", "Князь", "Князь", "Reach Князь rank", "Досягніть рангу Князь", "👑", "rank", 1900),
        ("rank_voivode", "Воєвода", "Воєвода", "Reach Воєвода rank", "Досягніть рангу Воєвода", "🗡️", "rank", 2000),
        ("rank_legenda", "Легенда", "Легенда", "Reach Легенда rank", "Досягніть рангу Легенда", "🌟", "rank", 2100),
        ("rank_volodar", "Володар", "Володар", "Reach Володар rank", "Досягніть рангу Володар", "💫", "rank", 2200),
        
        # Streak Achievements (8)
        ("streak_5", "Hot Streak", "Гаряча Серія", "Win 5 games in a row", "Виграйте 5 ігор поспіль", "🔥", "streak", 5),
        ("streak_10", "Lightning Streak", "Блискавка", "Win 10 games in a row", "Виграйте 10 ігор поспіль", "⚡", "streak", 10),
        ("streak_15", "Volcano", "Вулкан", "Win 15 games in a row", "Виграйте 15 ігор поспіль", "🌋", "streak", 15),
        ("streak_20", "Explosion", "Вибух", "Win 20 games in a row", "Виграйте 20 ігор поспіль", "💥", "streak", 20),
        ("streak_25", "Fireworks", "Феєрверк", "Win 25 games in a row", "Виграйте 25 ігор поспіль", "🎆", "streak", 25),
        ("streak_30", "Invincible", "Непереможний", "Win 30+ games in a row", "Виграйте 30+ ігор поспіль", "🌟", "streak", 30),
        ("streak_stability", "Stability", "Стабільність", "Maintain 10+ win streak twice", "Досягніть серії 10+ перемог двічі", "📊", "streak", 2),
        ("streak_precision", "Precision Streak", "Точність", "Win 5 games in a row without losing a piece", "Виграйте 5 ігор поспіль без втрати фігур", "🎯", "streak", 5),
        
        # Victory Achievements (15)
        ("victory_lucky", "Lucky", "Везунчик", "Win against opponent 200+ rating higher", "Виграйте проти суперника на 200+ рейтингу вище", "🎲", "victory", 200),
        ("victory_fortunate", "Fortunate", "Щасливчик", "Win against opponent 300+ rating higher", "Виграйте проти суперника на 300+ рейтингу вище", "🍀", "victory", 300),
        ("victory_jackpot", "Jackpot", "Джекпот", "Win against opponent 400+ rating higher", "Виграйте проти суперника на 400+ рейтингу вище", "🎰", "victory", 400),
        ("victory_comeback_100", "Comeback King", "Король Повернень", "Win from 100+ rating deficit", "Виграйте з дефіцитом 100+ рейтингу", "🔄", "victory", 100),
        ("victory_comeback_150", "Invincible Defender", "Непереможний Захисник", "Win from 150+ rating deficit", "Виграйте з дефіцитом 150+ рейтингу", "🛡️", "victory", 150),
        ("victory_lightning", "Lightning Victory", "Блискавка", "Win a game in under 25 moves", "Виграйте гру менше ніж за 25 ходів", "⚡", "victory", 25),
        ("victory_hurricane", "Hurricane", "Ураган", "Win a game in under 20 moves", "Виграйте гру менше ніж за 20 ходів", "💨", "victory", 20),
        ("victory_showman", "Showman", "Шоумен", "Win with perfect game (no pieces lost)", "Виграйте ідеальну гру (без втрати фігур)", "🎪", "victory", 1),
        ("victory_perfect_defense", "Perfect Defense", "Ідеальна Оборона", "Win 3 perfect games", "Виграйте 3 ідеальні гри", "🛡️", "victory", 3),
        ("victory_sniper", "Sniper", "Снайпер", "Win 10 games without losing a single piece total", "Виграйте 10 ігор без втрати жодної фігури", "🎯", "victory", 10),
        ("victory_speed_demon", "Speed Demon", "Швидкий Демон", "Win 3 games in one day", "Виграйте 3 гри за один день", "⏱️", "victory", 3),
        ("victory_marathoner", "Marathoner", "Марафонець", "Win 5 games in one day", "Виграйте 5 ігор за один день", "🏃", "victory", 5),
        ("victory_rocket", "Rocket", "Ракета", "Win 10 games in one day", "Виграйте 10 ігор за один день", "🚀", "victory", 10),
        ("victory_fortress", "Fortress", "Фортеця", "Win without losing any pieces", "Виграйте без втрати фігур", "🛡️", "victory", 1),
        ("victory_show", "Show", "Шоу", "Win 3 games without losing any pieces", "Виграйте 3 гри без втрати фігур", "🎪", "victory", 3),
        
        # Statistics Achievements (12)
        ("stats_positive_balance", "Positive Balance", "Позитивний Баланс", "Achieve 60%+ win rate (min 20 games)", "Досягніть 60%+ перемог (мін. 20 ігор)", "📈", "statistics", 60),
        ("stats_accuracy", "Accuracy", "Точність", "Achieve 70%+ win rate (min 30 games)", "Досягніть 70%+ перемог (мін. 30 ігор)", "🎯", "statistics", 70),
        ("stats_mastery", "Mastery", "Майстерність", "Achieve 80%+ win rate (min 50 games)", "Досягніть 80%+ перемог (мін. 50 ігор)", "👑", "statistics", 80),
        ("stats_perfection", "Perfection", "Досконалість", "Achieve 90%+ win rate (min 20 games)", "Досягніть 90%+ перемог (мін. 20 ігор)", "💯", "statistics", 90),
        ("stats_champion_wins", "Champion", "Чемпіон", "Win 50 games", "Виграйте 50 ігор", "🏆", "statistics", 50),
        ("stats_winner", "Winner", "Переможець", "Win 100 games", "Виграйте 100 ігор", "🥇", "statistics", 100),
        ("stats_king", "King", "Король", "Win 250 games", "Виграйте 250 ігор", "👑", "statistics", 250),
        ("stats_diamond", "Diamond", "Діамант", "Win 500 games", "Виграйте 500 ігор", "💎", "statistics", 500),
        ("stats_star", "Star", "Зірка", "Win 1,000 games", "Виграйте 1,000 ігор", "🌟", "statistics", 1000),
        ("stats_analyst", "Analyst", "Аналітик", "Play 50 games with 50%+ win rate", "Зіграйте 50 ігор з 50%+ перемог", "📊", "statistics", 50),
        ("stats_student", "Student", "Студент", "Learn from 20 losses", "Навчіться з 20 поразок", "🎓", "statistics", 20),
        ("stats_resilience", "Resilience", "Стійкість", "Win after 5 consecutive losses", "Виграйте після 5 поспіль поразок", "💪", "statistics", 5),
        
        # Gameplay Achievements (13)
        ("gameplay_first_move", "First Move", "Перший Хід", "Win a game where you moved first", "Виграйте гру, де ви ходили першими", "🎯", "gameplay", 1),
        ("gameplay_last_move", "Last Move", "Останній Хід", "Win a game where opponent moved first", "Виграйте гру, де суперник ходив першим", "🎲", "gameplay", 1),
        ("gameplay_balance", "Balance", "Рівновага", "Win 10 games as both colors", "Виграйте 10 ігор обома кольорами", "🔄", "gameplay", 10),
        ("gameplay_quick_reactor", "Quick Reactor", "Швидкий Реактор", "Win a game in under 5 minutes", "Виграйте гру менше ніж за 5 хвилин", "⚡", "gameplay", 5),
        ("gameplay_patience", "Patience", "Терпіння", "Win a game that lasted 50+ moves", "Виграйте гру, що тривала 50+ ходів", "🕐", "gameplay", 50),
        ("gameplay_wisdom", "Wisdom", "Мудрість", "Win a game that lasted 100+ moves", "Виграйте гру, що тривала 100+ ходів", "🕐", "gameplay", 100),
        ("gameplay_king_of_kings", "King of Kings", "Король Дамок", "Promote 5 pieces to kings in one game", "Перетворіть 5 фігур на дамок в одній грі", "👑", "gameplay", 5),
        ("gameplay_circus", "Circus", "Цирк", "Promote 10 pieces to kings in one game", "Перетворіть 10 фігур на дамок в одній грі", "🎪", "gameplay", 10),
        ("gameplay_precise_strike", "Precise Strike", "Точний Удар", "Capture 5+ pieces in one move", "Знищіть 5+ фігур за один хід", "🎯", "gameplay", 5),
        ("gameplay_mass_destruction", "Mass Destruction", "Масове Знищення", "Capture 8+ pieces in one game", "Знищіть 8+ фігур в одній грі", "💥", "gameplay", 8),
        ("gameplay_return", "Return", "Повернення", "Win after being down 3+ pieces", "Виграйте, будучи в мінусі на 3+ фігури", "🔄", "gameplay", 3),
        ("gameplay_willpower", "Willpower", "Сила Волі", "Win after being down 5+ pieces", "Виграйте, будучи в мінусі на 5+ фігур", "💪", "gameplay", 5),
        ("gameplay_fortress_gameplay", "Fortress Gameplay", "Фортеця", "Win without losing any pieces", "Виграйте без втрати фігур", "🛡️", "gameplay", 1),
        
        # Competitive Achievements (10)
        ("competitive_top_100", "Top 100", "Топ-100", "Reach top 100 in leaderboard", "Досягніть топ-100 в таблиці лідерів", "🥇", "competitive", 100),
        ("competitive_top_50", "Top 50", "Топ-50", "Reach top 50 in leaderboard", "Досягніть топ-50 в таблиці лідерів", "🥈", "competitive", 50),
        ("competitive_top_25", "Top 25", "Топ-25", "Reach top 25 in leaderboard", "Досягніть топ-25 в таблиці лідерів", "🥉", "competitive", 25),
        ("competitive_top_10", "Top 10", "Топ-10", "Reach top 10 in leaderboard", "Досягніть топ-10 в таблиці лідерів", "👑", "competitive", 10),
        ("competitive_top_5", "Top 5", "Топ-5", "Reach top 5 in leaderboard", "Досягніть топ-5 в таблиці лідерів", "💎", "competitive", 5),
        ("competitive_top_3", "Top 3", "Топ-3", "Reach top 3 in leaderboard", "Досягніть топ-3 в таблиці лідерів", "🌟", "competitive", 3),
        ("competitive_king", "King", "Король", "Reach #1 in leaderboard", "Досягніть #1 в таблиці лідерів", "👑", "competitive", 1),
        ("competitive_champion_week", "Champion Week", "Тиждень Чемпіона", "Be in top 10 for a week", "Будьте в топ-10 протягом тижня", "🏆", "competitive", 7),
        ("competitive_master_month", "Master Month", "Місяць Майстра", "Be in top 10 for a month", "Будьте в топ-10 протягом місяця", "📊", "competitive", 30),
        ("competitive_legend_year", "Legend Year", "Рік Легенди", "Be in top 10 for 3 months", "Будьте в топ-10 протягом 3 місяців", "🎯", "competitive", 90),
        
        # Time-Based Achievements (7)
        ("time_early_bird", "Early Bird", "Ранкова Пташка", "Win a game before 8 AM", "Виграйте гру до 8 ранку", "🌅", "time", 8),
        ("time_night_owl", "Night Owl", "Нічна Сова", "Win a game after midnight", "Виграйте гру після півночі", "🌙", "time", 0),
        ("time_daily_player", "Daily Player", "Щоденний Гравець", "Play a game every day for 7 days", "Зіграйте гру щодня протягом 7 днів", "📅", "time", 7),
        ("time_dedicated", "Dedicated", "Відданий", "Play a game every day for 30 days", "Зіграйте гру щодня протягом 30 днів", "📆", "time", 30),
        ("time_tireless_days", "Tireless Days", "Невтомний", "Play a game every day for 100 days", "Зіграйте гру щодня протягом 100 днів", "🗓️", "time", 100),
        ("time_weekend_warrior", "Weekend Warrior", "Вихідний Воїн", "Win 10 games on weekends", "Виграйте 10 ігор у вихідні", "🎉", "time", 10),
        ("time_consistency", "Consistency", "Стабільність", "Play at least one game per week for 3 months", "Зіграйте хоча б одну гру на тиждень протягом 3 місяців", "📊", "time", 12),
        
        # Special Achievements (4) - Removed 3 that require unavailable data
        ("special_holiday", "Holiday", "Святковий", "Win on a major holiday", "Виграйте на велике свято", "🎄", "special", 1),
        ("special_anniversary", "Anniversary", "Ювілей", "Play your first game", "Зіграйте свою першу гру", "🎊", "special", 1),
        ("special_target", "Target", "Мета", "Win exactly 100 rating in one game", "Виграйте рівно 100 рейтингу в одній грі", "🎯", "special", 100),
        ("special_random", "Random", "Випадковість", "Win with exactly 50% win rate after 20 games", "Виграйте з рівно 50% перемог після 20 ігор", "🎲", "special", 50),
        
        # Collection Achievements (6)
        ("collection_collector", "Collector", "Колекціонер", "Unlock 10 achievements", "Розблокуйте 10 досягнень", "🎖️", "collection", 10),
        ("collection_enthusiast", "Enthusiast", "Ентузіаст", "Unlock 25 achievements", "Розблокуйте 25 досягнень", "🏆", "collection", 25),
        ("collection_master", "Master Collector", "Майстер", "Unlock 50 achievements", "Розблокуйте 50 досягнень", "👑", "collection", 50),
        ("collection_expert", "Expert", "Експерт", "Unlock 75 achievements", "Розблокуйте 75 досягнень", "💎", "collection", 75),
        ("collection_legend", "Legend Collector", "Легенда", "Unlock 100+ achievements", "Розблокуйте 100+ досягнень", "🌟", "collection", 100),
        ("collection_completionist", "Completionist", "Завершальник", "Unlock all achievements", "Розблокуйте всі досягнення", "🎯", "collection", 0),  # 0 means all
    ]
    
    async with aiosqlite.connect(str(RATINGS_DB)) as db:
        for ach in achievements:
            try:
                await db.execute("""
                    INSERT INTO achievements 
                    (achievement_id, name, name_uk, description, description_uk, icon, category, requirement_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, ach)
            except aiosqlite.IntegrityError:
                print(f"  Warning: Achievement {ach[0]} already exists, skipping")
        await db.commit()
    
    print(f"✓ Populated {len(achievements)} achievements")

async def main():
    parser = argparse.ArgumentParser(description="Reset database for rating system overhaul")
    parser.add_argument("--confirm", action="store_true", help="Confirm database reset")
    parser.add_argument("--test", action="store_true", help="Use test database paths")
    
    args = parser.parse_args()
    
    if not args.confirm:
        print("=" * 60)
        print("WARNING: DATABASE RESET")
        print("=" * 60)
        print()
        print("This script will DELETE all existing player data!")
        print("Ratings, achievements, and statistics will be lost.")
        print()
        print("A backup will be created automatically.")
        print()
        print("Use --confirm flag to proceed:")
        print("  python scripts/reset_database.py --confirm")
        print()
        sys.exit(1)
    
    print("=" * 60)
    print("DATABASE RESET SCRIPT")
    print("=" * 60)
    print()
    print(f"Ratings DB: {RATINGS_DB}")
    print(f"Game Data DB: {GAMEDATA_DB}")
    print()
    
    try:
        await reset_ratings_database()
        await populate_achievements()
        
        print()
        print("=" * 60)
        print("✓ Database reset complete!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Update code to use new schema")
        print("2. Test with new database")
        print("3. Deploy to production")
        print()
    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR: Database reset failed!")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

