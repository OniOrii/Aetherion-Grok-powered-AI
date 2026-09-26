"""Easy general-knowledge trivia. Local bank plus Open Trivia DB."""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import logging
import secrets

logger = logging.getLogger("aetherion.trivia")

TRIVIA_MIN_BET = 10
TRIVIA_DEFAULT_BET = 100
TRIVIA_MAX_BET = 10_000
WIN_MULTI = 3.0
# Category 9 = General Knowledge. Easy multiple choice only.
OPENTDB = "https://opentdb.com/api.php?amount=1&category=9&difficulty=easy&type=multiple"

# Easy, mixed general knowledge. Used when the live feed is down or too wordy.
LOCAL_BANK: tuple[tuple[str, str, tuple[str, str, str], str], ...] = (
    ("What color do you get when you mix red and white?", "Pink", ("Purple", "Orange", "Brown"), "General"),
    ("How many days are in a leap year?", "366", ("365", "364", "360"), "General"),
    ("Which planet is known as the Red Planet?", "Mars", ("Venus", "Jupiter", "Mercury"), "Science"),
    ("How many continents are there?", "7", ("5", "6", "8"), "Geography"),
    ("What is the largest ocean?", "Pacific", ("Atlantic", "Indian", "Arctic"), "Geography"),
    ("Which animal is known as man's best friend?", "Dog", ("Cat", "Horse", "Parrot"), "General"),
    ("How many sides does a triangle have?", "3", ("4", "5", "6"), "Math"),
    ("What gas do people breathe in to live?", "Oxygen", ("Nitrogen", "Carbon", "Helium"), "Science"),
    ("Which country is famous for pizza and pasta?", "Italy", ("France", "Spain", "Greece"), "Food"),
    ("What is H2O?", "Water", ("Salt", "Air", "Sugar"), "Science"),
    ("How many minutes are in one hour?", "60", ("30", "45", "90"), "General"),
    ("Which fruit is yellow and curved?", "Banana", ("Lemon", "Mango", "Pear"), "Food"),
    ("What do bees make?", "Honey", ("Milk", "Silk", "Butter"), "Nature"),
    ("Which season comes after winter?", "Spring", ("Fall", "Summer", "Monsoon"), "General"),
    ("How many letters are in the English alphabet?", "26", ("24", "25", "30"), "Language"),
    ("What is the capital of the United States?", "Washington, D.C.", ("New York", "Los Angeles", "Chicago"), "Geography"),
    ("Which sport uses a bat, a ball, and bases?", "Baseball", ("Soccer", "Tennis", "Golf"), "Sports"),
    ("What color is a school bus in the United States?", "Yellow", ("Red", "Blue", "Green"), "General"),
    ("How many wheels does a bicycle have?", "2", ("1", "3", "4"), "General"),
    ("Which animal says meow?", "Cat", ("Dog", "Cow", "Duck"), "Nature"),
    ("What do you use to write on a blackboard?", "Chalk", ("Pen", "Crayon", "Marker"), "General"),
    ("Which meal is usually eaten in the morning?", "Breakfast", ("Dinner", "Lunch", "Supper"), "Food"),
    ("How many hours are in a day?", "24", ("12", "20", "48"), "General"),
    ("What is frozen water called?", "Ice", ("Steam", "Fog", "Rain"), "Science"),
    ("Which planet do we live on?", "Earth", ("Mars", "Venus", "Saturn"), "Science"),
    ("What is the opposite of hot?", "Cold", ("Warm", "Spicy", "Dry"), "Language"),
    ("How many strings does a standard guitar have?", "6", ("4", "5", "8"), "Music"),
    ("Which holiday uses a decorated tree and gifts?", "Christmas", ("Halloween", "Easter", "Thanksgiving"), "General"),
    ("What color are emeralds?", "Green", ("Blue", "Red", "Purple"), "General"),
    ("Which ocean is on the east coast of the United States?", "Atlantic", ("Pacific", "Indian", "Arctic"), "Geography"),
    ("How many zeros are in one thousand?", "3", ("2", "4", "1"), "Math"),
    ("What do you call a baby dog?", "Puppy", ("Kitten", "Calf", "Cub"), "Nature"),
    ("Which shape has four equal sides?", "Square", ("Rectangle", "Triangle", "Circle"), "Math"),
    ("What is the main language spoken in Brazil?", "Portuguese", ("Spanish", "French", "English"), "Language"),
    ("How many players are on the field for one soccer team?", "11", ("9", "10", "12"), "Sports"),
    ("Which bird is known for saying 'nevermore' in a famous poem?", "Raven", ("Eagle", "Owl", "Parrot"), "Literature"),
    ("What do plants need from the sun to make food?", "Light", ("Wind", "Sound", "Sand"), "Science"),
    ("Which month has 28 days in a common year?", "February", ("April", "June", "September"), "General"),
    ("What is 5 + 7?", "12", ("10", "11", "13"), "Math"),
    ("Which drink is made from roasted beans?", "Coffee", ("Tea", "Milk", "Soda"), "Food"),
)


@dataclass
class TriviaQuestion:
    prompt: str
    answers: list[str]
    correct_index: int
    category: str
    source: str

    @property
    def correct(self) -> str:
        return self.answers[self.correct_index]


def _clean(text: str) -> str:
    return unescape(str(text or "")).strip()


def _too_wordy(prompt: str, answers: list[str]) -> bool:
    if len(prompt) > 140:
        return True
    if any(len(item) > 42 for item in answers):
        return True
    return False


def _from_local() -> TriviaQuestion:
    prompt, correct, wrongs, category = secrets.choice(LOCAL_BANK)
    answers = [correct, *wrongs]
    secrets.SystemRandom().shuffle(answers)
    return TriviaQuestion(
        prompt=prompt,
        answers=answers,
        correct_index=answers.index(correct),
        category=category,
        source="house",
    )


async def fetch_question() -> TriviaQuestion:
    try:
        import httpx

        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(OPENTDB)
            resp.raise_for_status()
            payload = resp.json()
        rows = payload.get("results") or []
        if not rows:
            raise ValueError("empty opentdb")
        row = rows[0]
        correct = _clean(row.get("correct_answer"))
        wrongs = [_clean(item) for item in (row.get("incorrect_answers") or [])]
        prompt = _clean(row.get("question"))
        if not prompt or not correct or len(wrongs) != 3:
            raise ValueError("bad opentdb shape")
        answers = [correct, *wrongs]
        if _too_wordy(prompt, answers):
            raise ValueError("live question too wordy")
        secrets.SystemRandom().shuffle(answers)
        return TriviaQuestion(
            prompt=prompt,
            answers=answers,
            correct_index=answers.index(correct),
            category=_clean(row.get("category")) or "General",
            source="live",
        )
    except Exception:
        logger.info("trivia live feed missed, using house bank")
        return _from_local()
