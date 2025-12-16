"""
Rank System for Ukrainian Checkers Bot
Defines Ukrainian-themed ranks based on ELO rating.
"""

from typing import Optional, Dict, Tuple

# Rank definitions: (min_rating, name_uk, name_en, icon, description_uk, description_en)
RANKS = [
    (0, "Новачок", "Novice", "🌱", "Початківець у світі шашок", "A beginner in the world of checkers"),
    (800, "Новачок", "Novice", "🌱", "Початківець у світі шашок", "A beginner in the world of checkers"),
    (1000, "Шашкар", "Shashkar", "🎯", "Досвідчений гравець", "An experienced player"),
    (1100, "Учень", "Student", "📚", "Учень майстрів", "Student of masters"),
    (1200, "Гравець", "Player", "🎮", "Справжній гравець", "A true player"),
    (1300, "Майстер", "Master", "⚔️", "Майстер гри", "Master of the game"),
    (1400, "Ветеран", "Veteran", "🛡️", "Ветеран битв", "Veteran of battles"),
    (1500, "Чемпіон", "Champion", "🏆", "Чемпіон турнірів", "Tournament champion"),
    (1600, "Козак", "Cossack", "⚡", "Вільний воїн", "Free warrior"),
    (1700, "Гетьман", "Hetman", "👑", "Володар поля", "Lord of the field"),
    (1800, "Богатир", "Bogatyr", "⚔️", "Богатир-воїн", "Bogatyr warrior"),
    (1900, "Князь", "Prince", "👑", "Князь шашок", "Prince of checkers"),
    (2000, "Воєвода", "Voivode", "🗡️", "Воєвода армії", "Voivode of the army"),
    (2100, "Легенда", "Legend", "🌟", "Жива легенда", "Living legend"),
    (2200, "Володар", "Ruler", "💫", "Володар всіх", "Ruler of all"),
]

def get_rank(rating: int) -> Dict[str, any]:
    """
    Get rank information for a given rating.
    
    Args:
        rating: Player's current ELO rating
        
    Returns:
        Dictionary with rank information:
        - name_uk: Ukrainian name
        - name_en: English name
        - icon: Rank icon/emoji
        - min_rating: Minimum rating for this rank
        - description_uk: Ukrainian description
        - description_en: English description
    """
    # Find the highest rank the player qualifies for
    for i in range(len(RANKS) - 1, -1, -1):
        min_rating, name_uk, name_en, icon, desc_uk, desc_en = RANKS[i]
        if rating >= min_rating:
            # Get next rank info for progress calculation
            next_rank = None
            if i < len(RANKS) - 1:
                next_min, next_name_uk, next_name_en, next_icon, _, _ = RANKS[i + 1]
                next_rank = {
                    "min_rating": next_min,
                    "name_uk": next_name_uk,
                    "name_en": next_name_en,
                    "icon": next_icon,
                }
            
            return {
                "name_uk": name_uk,
                "name_en": name_en,
                "icon": icon,
                "min_rating": min_rating,
                "description_uk": desc_uk,
                "description_en": desc_en,
                "next_rank": next_rank,
            }
    
    # Fallback to lowest rank
    min_rating, name_uk, name_en, icon, desc_uk, desc_en = RANKS[0]
    return {
        "name_uk": name_uk,
        "name_en": name_en,
        "icon": icon,
        "min_rating": min_rating,
        "description_uk": desc_uk,
        "description_en": desc_en,
        "next_rank": RANKS[1] if len(RANKS) > 1 else None,
    }

def get_rank_progress(rating: int) -> Tuple[float, int, int]:
    """
    Calculate progress to next rank.
    
    Args:
        rating: Player's current ELO rating
        
    Returns:
        Tuple of (progress_percentage, current_rating, next_rank_rating)
        If at max rank, returns (100.0, rating, rating)
    """
    current_rank = get_rank(rating)
    next_rank = current_rank.get("next_rank")
    
    if not next_rank:
        # At max rank
        return (100.0, rating, rating)
    
    current_min = current_rank["min_rating"]
    next_min = next_rank["min_rating"]
    
    # Calculate progress within current rank
    rating_range = next_min - current_min
    progress = rating - current_min
    
    if rating_range == 0:
        percentage = 100.0
    else:
        percentage = min(100.0, (progress / rating_range) * 100.0)
    
    return (percentage, rating, next_min)

def get_rank_by_name(name_uk: str) -> Optional[Dict[str, any]]:
    """
    Get rank information by Ukrainian name.
    
    Args:
        name_uk: Ukrainian rank name
        
    Returns:
        Rank dictionary or None if not found
    """
    for min_rating, rank_name_uk, name_en, icon, desc_uk, desc_en in RANKS:
        if rank_name_uk == name_uk:
            return {
                "name_uk": rank_name_uk,
                "name_en": name_en,
                "icon": icon,
                "min_rating": min_rating,
                "description_uk": desc_uk,
                "description_en": desc_en,
            }
    return None

