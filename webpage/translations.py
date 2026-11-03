"""All user-visible text, per language.

Items are identified by their Czech name from assets/items.md (that is what
the results CSV stores); ITEM_NAMES only changes what the participant sees.
"""

LANGUAGES = {"cs": "Čeština", "en": "English"}
DEFAULT_LANGUAGE = "cs"

UI = {
    "cs": {
        "title": "Rozpoznávání částečně zakrytých předmětů",
        "choose_language": "Jazyk",
        "thanks": "Děkujeme, že se účastníte našeho experimentu do předmětu Kognitivní systémy.",
        "instr_count": "Uvidíte postupně <strong>{n} obrázků</strong>. Na každém je předmět, který je částečně zakrytý jiným předmětem.",
        "instr_exposure": "Každý obrázek se zobrazí jen na <strong>{s} s</strong> a pak zmizí.",
        "instr_choose": "Poté vyberte ze čtyř možností, <strong>který předmět byl zakrytý</strong>.",
        "instr_speed": "Odpovídejte <strong>co nejrychleji a zároveň co nejpřesněji</strong>. Pokud si nejste jistí, tipněte si.",
        "instr_anon": "Test je anonymní a trvá přibližně 1–2 minuty.",
        "continue": "Pokračovat",
        "training_title": "Nejdřív si prohlédněte předměty",
        "training_text": "Takto vypadají předměty, které budete v testu hledat, a takto se budou jmenovat v odpovědích.",
        "start": "Začít test",
        "progress": "Obrázek {i} / {n}",
        "question": "Který předmět byl částečně zakrytý?",
        "done": "Hotovo, děkujeme!",
        "summary": "Správně: {correct} / {total} · celkový čas {seconds} s",
        "saved": "Výsledky byly uloženy. Okno můžete zavřít.",
    },
    "en": {
        "title": "Recognising partially hidden objects",
        "choose_language": "Language",
        "thanks": "Thank you for taking part in our experiment for the Cognitive Systems course.",
        "instr_count": "You will see <strong>{n} images</strong>, one at a time. Each shows an object that is partly hidden behind another object.",
        "instr_exposure": "Each image is shown for only <strong>{s} s</strong> and then disappears.",
        "instr_choose": "Then choose from four options <strong>which object was hidden</strong>.",
        "instr_speed": "Answer <strong>as quickly and as accurately as you can</strong>. If you are not sure, take a guess.",
        "instr_anon": "The test is anonymous and takes about 1–2 minutes.",
        "continue": "Continue",
        "training_title": "First, have a look at the objects",
        "training_text": "This is what the objects you will look for in the test look like, and the names they will have in the answers.",
        "start": "Start test",
        "progress": "Image {i} / {n}",
        "question": "Which object was partly hidden?",
        "done": "Done, thank you!",
        "summary": "Correct: {correct} / {total} · total time {seconds} s",
        "saved": "Your results have been saved. You can close this window.",
    },
}

ITEM_NAMES = {
    "en": {
        "Kniha": "Book",
        "Sešit": "Exercise book",
        "Časopis": "Magazine",
        "Poznámkový blok": "Notepad",
        "Hrnek": "Mug",
        "Sklenice": "Glass",
        "Miska": "Bowl",
        "Šálek s podšálkem": "Cup and saucer",
        "Tužka": "Pencil",
        "Pero": "Pen",
        "Fix": "Marker",
        "Zvýrazňovač": "Highlighter",
        "Lžíce": "Spoon",
        "Vidlička": "Fork",
        "Nůž": "Knife",
        "Špachtle": "Spatula",
        "Zubní kartáček": "Toothbrush",
        "Holicí strojek": "Razor",
        "Hřeben": "Comb",
        "Kartáč na vlasy": "Hairbrush",
        "Kladivo": "Hammer",
        "Šroubovák": "Screwdriver",
        "Kleště": "Pliers",
        "Klíč na matice": "Wrench",
    },
}


def item_name(item: str, lang: str) -> str:
    return ITEM_NAMES.get(lang, {}).get(item, item)
