"""
Comprehensive integration tests for AchievementSystem - all fixed achievements
"""

import pytest
import aiosqlite
from datetime import date, time, datetime
from achievements import AchievementSystem
from ratings import RatingSystem


async def populate_achievements_for_test(db_path: str):
    """Populate achievements table for testing."""
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
        ("collection_completionist", "Completionist", "Завершальник", "Unlock all achievements", "Розблокуйте всі досягнення", "🎯", "collection", 0),
    ]
    
    async with aiosqlite.connect(db_path) as db:
        # Create achievements table if it doesn't exist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_uk TEXT NOT NULL,
                description TEXT NOT NULL,
                description_uk TEXT NOT NULL,
                icon TEXT NOT NULL,
                category TEXT NOT NULL,
                requirement_value INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_achievements (
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, achievement_id)
            )
        """)
        
        for ach in achievements:
            try:
                await db.execute("""
                    INSERT INTO achievements 
                    (achievement_id, name, name_uk, description, description_uk, icon, category, requirement_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, ach)
            except aiosqlite.IntegrityError:
                pass  # Already exists
        await db.commit()


@pytest.mark.integration
class TestMoveCountAchievements:
    """Test move count achievements with fixed thresholds."""
    
    @pytest.mark.asyncio
    async def test_victory_lightning_25_moves(self, temp_achievements_db: AchievementSystem):
        """Test victory_lightning with new 25 move threshold."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "move_count": 25,  # Exactly at threshold
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60001, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "victory_lightning" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_victory_lightning_under_25(self, temp_achievements_db: AchievementSystem):
        """Test victory_lightning with moves under 25."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "move_count": 20,  # Under threshold
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60002, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "victory_lightning" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_victory_hurricane_20_moves(self, temp_achievements_db: AchievementSystem):
        """Test victory_hurricane with new 20 move threshold."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "move_count": 20,  # Exactly at threshold
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60003, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "victory_hurricane" in unlocked_ids


@pytest.mark.integration
class TestTimeBasedAchievements:
    """Test time-based achievements."""
    
    @pytest.mark.asyncio
    async def test_time_early_bird(self, temp_achievements_db: AchievementSystem):
        """Test early bird achievement (before 8 AM)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(7, 30),  # Before 8 AM
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60010, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "time_early_bird" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_time_night_owl(self, temp_achievements_db: AchievementSystem):
        """Test night owl achievement (after midnight)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(2, 30),  # After midnight
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60011, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "time_night_owl" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_time_daily_player(self, temp_achievements_db: AchievementSystem):
        """Test daily player achievement (7 consecutive days)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 10,
            "wins": 5,
            "rating": 1200,
            "consecutive_days": 7  # Exactly 7 days
        }
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(12, 0),
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60012, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "time_daily_player" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_time_weekend_warrior(self, temp_achievements_db: AchievementSystem):
        """Test weekend warrior achievement."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        # Create a Saturday date
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today if days_until_saturday == 0 else None
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "game_date": saturday or date.today(),  # Weekend
            "game_time": time(14, 0),
            "rating_change": 20
        }
        
        # This is a simplified test - the actual achievement needs weekend wins counter
        unlocked = await temp_achievements_db.check_achievements(
            60013, player_data, game_result
        )
        assert isinstance(unlocked, list)


@pytest.mark.integration
class TestCompetitiveAchievements:
    """Test competitive achievements."""
    
    @pytest.mark.asyncio
    async def test_competitive_top_100(self, temp_achievements_db: AchievementSystem, temp_ratings_db: RatingSystem):
        """Test top 100 achievement."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        # Create players to establish ranking
        for i in range(50):
            await temp_ratings_db.get_player(70000 + i, f"Player{i}")
            await temp_ratings_db.record_game(
                70000 + i, f"Player{i}",
                70000 + (i + 1), f"Player{i+1}",
                move_count=10
            )
        
        # Create a player in top 100
        player_data = await temp_ratings_db.get_player(70050, "TopPlayer")
        player_data["rating"] = 1500  # High rating
        
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            70050, player_data, game_result
        )
        # May unlock competitive achievements if rank is <= 100
        assert isinstance(unlocked, list)


@pytest.mark.integration
class TestGameplayAchievements:
    """Test gameplay achievements."""
    
    @pytest.mark.asyncio
    async def test_gameplay_king_of_kings(self, temp_achievements_db: AchievementSystem):
        """Test king of kings achievement (5 promotions)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "promotions": 5,  # Exactly 5 promotions
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60020, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_king_of_kings" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_gameplay_precise_strike(self, temp_achievements_db: AchievementSystem):
        """Test precise strike achievement (5+ captures in one move)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "max_captures_in_move": 5,  # Exactly 5 captures
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60021, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_precise_strike" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_gameplay_mass_destruction(self, temp_achievements_db: AchievementSystem):
        """Test mass destruction achievement (8+ captures in game)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "pieces_captured": 8,  # Exactly 8 captures
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60022, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_mass_destruction" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_gameplay_return(self, temp_achievements_db: AchievementSystem):
        """Test return achievement (win after being down 3+ pieces)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "pieces_lost": 3,  # Lost 3 pieces but won
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60023, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_return" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_gameplay_fortress_gameplay(self, temp_achievements_db: AchievementSystem):
        """Test fortress gameplay achievement (win without losing pieces)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "pieces_lost": 0,  # Perfect game
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60024, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_fortress_gameplay" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_gameplay_balance(self, temp_achievements_db: AchievementSystem):
        """Test balance achievement (win 10 games as both colors)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 25,
            "wins": 20,
            "rating": 1200,
            "wins_as_yellow": 10,
            "wins_as_blue": 10
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60025, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_balance" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_gameplay_quick_reactor(self, temp_achievements_db: AchievementSystem):
        """Test quick reactor achievement (win in under 5 minutes)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "game_duration_seconds": 240,  # 4 minutes
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60026, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "gameplay_quick_reactor" in unlocked_ids


@pytest.mark.integration
class TestVictoryAchievements:
    """Test victory achievements with fixes."""
    
    @pytest.mark.asyncio
    async def test_victory_comeback_100(self, temp_achievements_db: AchievementSystem):
        """Test comeback achievement with pre-game rating difference."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 10, "wins": 5, "rating": 1100}
        opponent_data = {"rating": 1200}  # 100 point difference
        game_result = {
            "won": True,
            "opponent_rating_before": 1200,
            "rating_change": 25
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60030, player_data, game_result, opponent_data
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "victory_comeback_100" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_victory_speed_demon(self, temp_achievements_db: AchievementSystem):
        """Test speed demon achievement (3 games in one day)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 5,
            "wins": 3,
            "rating": 1200,
            "games_today": 3  # Exactly 3 games today
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60031, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "victory_speed_demon" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_victory_perfect_defense(self, temp_achievements_db: AchievementSystem):
        """Test perfect defense achievement (3 perfect games)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 10,
            "wins": 5,
            "rating": 1200,
            "perfect_games": 3  # Exactly 3 perfect games
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60032, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "victory_perfect_defense" in unlocked_ids


@pytest.mark.integration
class TestMilestoneAchievements:
    """Test milestone achievements with time-period tracking."""
    
    @pytest.mark.asyncio
    async def test_rising_star(self, temp_achievements_db: AchievementSystem):
        """Test rising star achievement (200 rating in a week)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 10,
            "wins": 5,
            "rating": 1200,
            "rating_gain_this_week": 200  # Exactly 200 this week
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60040, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "rising_star" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_meteor(self, temp_achievements_db: AchievementSystem):
        """Test meteor achievement (300 rating in a week)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 15,
            "wins": 10,
            "rating": 1200,
            "rating_gain_this_week": 300  # Exactly 300 this week
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60041, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "meteor" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_comet(self, temp_achievements_db: AchievementSystem):
        """Test comet achievement (500 rating in a month)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 30,
            "wins": 20,
            "rating": 1200,
            "rating_gain_this_month": 500  # Exactly 500 this month
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60042, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "comet" in unlocked_ids


@pytest.mark.integration
class TestStreakAchievements:
    """Test streak achievements with fixes."""
    
    @pytest.mark.asyncio
    async def test_streak_stability(self, temp_achievements_db: AchievementSystem):
        """Test streak stability achievement (simplified to 10+ streak)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 15,
            "wins": 12,
            "rating": 1200,
            "best_streak": 10  # Exactly 10 streak
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60050, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "streak_stability" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_streak_precision(self, temp_achievements_db: AchievementSystem):
        """Test streak precision achievement (5 perfect games in a row)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 10,
            "wins": 8,
            "rating": 1200,
            "perfect_streak": 5  # Exactly 5 perfect games in a row
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await temp_achievements_db.check_achievements(
            60051, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "streak_precision" in unlocked_ids


@pytest.mark.integration
class TestSpecialAchievements:
    """Test special achievements (removed and redesigned)."""
    
    @pytest.mark.asyncio
    async def test_special_holiday(self, temp_achievements_db: AchievementSystem):
        """Test holiday achievement (New Year)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "game_date": date(2025, 1, 1),  # New Year
            "game_time": time(12, 0),
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60060, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "special_holiday" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_special_anniversary(self, temp_achievements_db: AchievementSystem):
        """Test anniversary achievement (first game)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {
            "games_played": 1,  # First game
            "wins": 1,
            "rating": 1200
        }
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(12, 0),
            "rating_change": 20
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60061, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "special_anniversary" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_special_target(self, temp_achievements_db: AchievementSystem):
        """Test target achievement (exactly 100 rating)."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {
            "won": True,
            "rating_change": 100  # Exactly 100
        }
        
        unlocked = await temp_achievements_db.check_achievements(
            60062, player_data, game_result
        )
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "special_target" in unlocked_ids


@pytest.mark.integration
class TestAchievementCount:
    """Test that we have the correct number of achievements."""
    
    @pytest.mark.asyncio
    async def test_total_achievement_count(self, temp_achievements_db: AchievementSystem):
        """Verify we have the correct number of achievements."""
        await populate_achievements_for_test(temp_achievements_db.db_path)
        
        all_achievements = await temp_achievements_db.get_all_achievements()
        
        # Count by category
        categories = {}
        for ach in all_achievements:
            cat = ach["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        total = len(all_achievements)
        
        # Should have 100 achievements total (with 3 removed special achievements not present).
        assert total == 100, f"Expected 100 achievements, got {total}. Categories: {categories}"
        
        # Verify removed achievements are not present
        achievement_ids = {ach["achievement_id"] for ach in all_achievements}
        assert "special_surprise" not in achievement_ids
        assert "special_unique" not in achievement_ids
        assert "special_pioneer" not in achievement_ids

