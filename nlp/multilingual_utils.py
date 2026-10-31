"""Lexicons and helpers shared by the multilingual NLP modules.

Everything here is plain data + small functions so it is easy to extend.
"""

# ---------------------------------------------------------------------------
# Romanized Tamil ("Tanglish") marker words used for language identification.
# ---------------------------------------------------------------------------
TANGLISH_MARKERS = {
    "romba", "rombha", "romba", "nalla", "nallaa", "nalladhu", "iruku", "irukku", "iruka", "irukkum",
    "illa", "illai", "ila", "illaye", "illama", "ilaye", "illaiye", "ennada", "enna", "epdi", "eppadi",
    "pesuranga", "padikkuranga", "solli", "sollikodukkuranga", "sollikudukkuranga", "puriyala", "puriyudhu",
    "puriyuthu", "purila", "theriyala", "mosam", "mokkai", "semma", "super", "vera", "level", "waste",
    "kammi", "kammiya", "korachu", "kuraivu", "athigam", "adhigam", "romba", "konjam", "ellam", "ella",
    "oru", "oru", "inga", "anga", "ange", "inge", "naan", "nan", "naa", "unga", "unnga", "enga", "avanga",
    "avar", "ivar", "sir", "madam", "vaathiyar", "aasiriyar", "aasiriyar", "padam", "paadam", "class",
    "kathukkuduthanga", "kathukudukkuranga", "kudukkuranga", "kudukuranga", "vandhuchu", "varala",
    "varadhu", "varathu", "work", "aagala", "aagudhu", "aaguthu", "agala", "agudhu", "panna", "pannunga",
    "pannuranga", "pannala", "panraanga", "pannanum", "venum", "vendam", "vendaam", "podhum", "podum",
    "theva", "thevai", "kedaikala", "kidaikala", "kidaikkala", "kedaikkala", "kedaikum", "kidaikum",
    "slow", "nalla", "azhaga", "alaga", "arumai", "arumaiya", "sirappu", "sirappa", "mosamaana",
    "kashtam", "kastam", "kashtama", "kasta", "thollai", "payanilla", "payanulla", "payan", "pidikkum",
    "pidikala", "pidichiruku", "pidikkala", "theliva", "theliva", "thelivaa", "puriyum", "puriyara",
    "pola", "mathiri", "madhiri", "ippo", "ippodhu", "appo", "eppo", "yaaru", "yaar", "evlo", "evvalavu",
    "kandippa", "kandippaa", "seri", "sari", "aama", "ama", "illanga", "irukanga", "irukkanga", "irukku",
    "ah", "da", "dei", "pa", "la", "nu", "ndra", "thaan", "dhaan", "than", "um", "aana", "aanaa",
    "aanal", "ana", "but", "ellarukum", "ellarukkum", "padikka", "padika", "kathukka", "kathukanum",
    "vasathi", "vasadhi", "vasathigal", "vasadhigal", "kuraivaa", "kuraivaga", "kammiyaa", "kammiyaa",
}
# remove generic English words that would cause false positives in pure English text
TANGLISH_MARKERS -= {"super", "slow", "class", "work", "but", "sir", "madam", "la", "da", "pa", "um",
                     "ah", "oru", "level", "waste", "vera", "sari", "nu", "than"}

HINGLISH_MARKERS = {
    "bahut", "bohot", "bhot", "accha", "acha", "achha", "achcha", "bura", "kharab", "theek", "thik",
    "hai", "hain", "tha", "thi", "the", "nahi", "nahin", "nhi", "mat", "kam", "zyada", "jyada", "bilkul",
    "lekin", "magar", "par", "aur", "ya", "kyunki", "isliye", "sir", "ka", "ki", "ke", "ko", "se", "mein",
    "me", "mai", "hum", "hamare", "humare", "aap", "padhate", "padhata", "padhai", "samajh", "samajhta",
    "samjh", "samajh", "sikhate", "sikhata", "shikshak", "adhyapak", "kaksha", "suvidha", "suvidhaen",
    "kaam", "karta", "karte", "kar", "raha", "rahi", "rahe", "chahiye", "milta", "milti", "milte",
    "dhima", "dheema", "tez", "badhiya", "mast", "bekar", "faltu", "ganda", "sahi", "galat", "kuch",
    "koi", "sab", "sabhi", "bhi", "toh", "to", "yeh", "ye", "woh", "wo", "is", "us", "kaise", "kyun",
    "kya", "kab", "kahan", "abhi", "ab", "pehle", "baad", "wala", "wali", "wale", "lagta", "lagti",
    "hota", "hoti", "hote", "hoga", "hogi", "diya", "diye", "dena", "do", "lab", "pariksha", "exam",
}
HINGLISH_MARKERS -= {"is", "to", "the", "me", "do", "sir", "lab", "exam", "par", "kar", "us", "ab", "ya", "ye"}

ENGLISH_STOPWORDS = {
    "the", "is", "are", "was", "were", "and", "very", "good", "not", "but", "with", "for", "this", "that",
    "of", "in", "to", "a", "an", "it", "we", "our", "they", "their", "have", "has", "need", "needs",
    "more", "too", "so", "very", "really", "from", "on", "at", "by", "be", "been", "should", "could",
}

# ---------------------------------------------------------------------------
# Tanglish / Hinglish normalisation: map spelling variants to canonical tokens
# and translate the most important Romanized words into English "concept"
# tokens so one shared English-centred feature space can serve all languages.
# ---------------------------------------------------------------------------
ROMAN_SPELLING_VARIANTS = {
    # intensifiers / quality
    "rombha": "romba", "romba": "romba", "rmba": "romba", "ramba": "romba",
    "nallaa": "nalla", "nalladhu": "nalla", "nalla": "nalla", "nallaaa": "nalla",
    "irukku": "iruku", "irukkuu": "iruku", "iruka": "iruku", "irukkum": "iruku", "irukkudhu": "iruku",
    "illai": "illa", "illaye": "illa", "ilaye": "illa", "ila": "illa", "illaiye": "illa", "illanga": "illa",
    "mokka": "mokkai", "mokkaa": "mokkai",
    "kashtam": "kastam", "kashta": "kastam",
    "kedaikala": "kidaikala", "kedaikkala": "kidaikala", "kidaikkala": "kidaikala",
    "puriyala": "puriyala", "purila": "puriyala", "puriyaala": "puriyala",
    "varala": "varala", "varalai": "varala",
    "aagala": "agala", "aagudhu": "agudhu", "aaguthu": "agudhu",
    "adhigam": "athigam", "kuraivu": "kammi", "korachu": "kammi", "kammiya": "kammi", "kuraivaga": "kammi",
    "bahut": "bahut", "bohot": "bahut", "bhot": "bahut", "bhut": "bahut",
    "acha": "accha", "achha": "accha", "achcha": "accha",
    "nahin": "nahi", "nhi": "nahi", "nai": "nahi",
    "dheema": "dhima", "dhimaa": "dhima",
    "thik": "theek",
}

# Romanized word -> English concept token(s)
ROMAN_TO_ENGLISH = {
    # Tamil romanized
    "romba": "very", "athigam": "very",
    "nalla": "good", "arumai": "excellent", "arumaiya": "excellent", "super": "good", "semma": "excellent",
    "sirappu": "excellent", "sirappa": "excellent", "azhaga": "good", "alaga": "good", "theliva": "clear",
    "thelivaa": "clear",
    "mosam": "bad", "mosamaana": "bad", "mokkai": "bad", "kastam": "difficult", "thollai": "problem",
    "waste": "waste", "payanilla": "useless", "kammi": "less poor",
    "illa": "not available", "kidaikala": "not available", "varala": "not working", "agala": "not working",
    "puriyala": "not understand", "pidikala": "dislike", "pidikkala": "dislike", "pidikkum": "like",
    "pidichiruku": "like", "venum": "need", "thevai": "need", "theva": "need",
    "aasiriyar": "teacher", "vaathiyar": "teacher", "padam": "lesson", "paadam": "lesson",
    "vasathi": "facilities", "vasadhi": "facilities", "vasathigal": "facilities", "vasadhigal": "facilities",
    "mathiri": "like", "madhiri": "like",
    "kathukkuduthanga": "teach", "kathukudukkuranga": "teach", "sollikodukkuranga": "teach",
    "sollikudukkuranga": "teach", "padikkuranga": "teach", "pesuranga": "speak",
    "aana": "but", "aanaa": "but", "aanal": "but", "ana": "but",
    # Hindi romanized
    "bahut": "very", "bilkul": "completely", "accha": "good", "badhiya": "excellent", "mast": "excellent",
    "sahi": "good", "bura": "bad", "kharab": "bad", "bekar": "useless", "faltu": "useless", "ganda": "bad",
    "dhima": "slow", "tez": "fast", "kam": "less poor", "zyada": "more", "jyada": "more",
    "theek": "okay", "lekin": "but", "magar": "but", "nahi": "not", "padhate": "teach", "padhata": "teach",
    "padhai": "study", "samajh": "understand", "shikshak": "teacher", "adhyapak": "teacher",
    "suvidha": "facilities", "suvidhaen": "facilities", "kaksha": "classroom", "pariksha": "exam",
    "chahiye": "need", "milta": "available", "milte": "available", "milti": "available",
}

# Native script words -> English concept tokens (sentiment- and aspect-relevant vocabulary).
TAMIL_TO_ENGLISH = {
    "ஆசிரியர்": "teacher", "ஆசிரியர்கள்": "teachers", "பேராசிரியர்": "professor", "விரிவுரையாளர்": "lecturer",
    "கற்பிக்கிறார்": "teaches", "கற்பிக்கிறார்கள்": "teaches", "கற்பித்தல்": "teaching", "கற்பிப்பது": "teaching",
    "நன்றாக": "well good", "நன்று": "good", "நல்ல": "good", "நல்லது": "good", "மிகவும்": "very",
    "சிறப்பாக": "excellent", "சிறப்பு": "excellent", "அருமை": "excellent", "அருமையாக": "excellent",
    "தெளிவாக": "clear", "தெளிவு": "clear", "புரிகிறது": "understand", "புரியவில்லை": "not understand",
    "குறைவாக": "less poor", "குறைவு": "less poor", "குறைபாடு": "poor", "மோசம்": "bad", "மோசமாக": "bad",
    "மோசமான": "bad", "கெட்ட": "bad", "வசதி": "facilities", "வசதிகள்": "facilities", "வசதிகளும்": "facilities",
    "லேப்": "lab", "ஆய்வகம்": "laboratory", "ஆய்வகங்கள்": "laboratory", "கணினி": "computer",
    "கணினிகள்": "computers", "உபகரணங்கள்": "equipment", "உபகரணம்": "equipment", "வகுப்பறை": "classroom",
    "பாடத்திட்டம்": "syllabus", "பாடம்": "lesson", "பாடங்கள்": "lessons", "பாடத்திட்டத்தில்": "syllabus",
    "உள்ளடக்கம்": "content", "கடினம்": "difficult", "கடினமாக": "difficult", "எளிது": "easy", "எளிமையாக": "easy",
    "இணையம்": "internet", "இணைய": "internet", "வைஃபை": "wifi", "வைபை": "wifi", "நெட்வொர்க்": "network",
    "மெதுவாக": "slow", "மெதுவான": "slow", "வேகம்": "speed", "வேகமாக": "fast", "இல்லை": "not available",
    "இல்லாததால்": "not available", "கிடைக்கவில்லை": "not available", "வேலை": "work",
    "செய்யவில்லை": "not working", "வேலை செய்யவில்லை": "not working", "ஆனால்": "but", "மற்றும்": "and",
    "உள்ளது": "is", "உள்ளன": "are", "இருக்கிறது": "is", "பயனுள்ள": "useful", "பயனில்லை": "useless",
    "தாமதம்": "delay", "பிரச்சனை": "problem", "பிரச்சினை": "problem", "சிரமம்": "difficulty",
    "மகிழ்ச்சி": "happy", "திருப்தி": "satisfied", "அதிருப்தி": "dissatisfied", "தேவை": "need",
    "மேம்படுத்த": "improve", "பராமரிப்பு": "maintenance", "சுத்தம்": "clean", "அழுக்கு": "dirty",
    "பயிற்சி": "practical", "செயல்முறை": "practical", "புத்தகங்கள்": "books", "நூலகம்": "library",
}

HINDI_TO_ENGLISH = {
    "शिक्षक": "teacher", "शिक्षकों": "teachers", "अध्यापक": "teacher", "प्राध्यापक": "professor",
    "पढ़ाते": "teach", "पढ़ाता": "teach", "पढ़ाई": "study", "पढ़ाना": "teaching", "शिक्षण": "teaching",
    "समझाते": "explain", "समझाना": "explanation", "बहुत": "very", "अच्छा": "good", "अच्छी": "good",
    "अच्छे": "good", "बढ़िया": "excellent", "शानदार": "excellent", "उत्कृष्ट": "excellent", "बेहतरीन": "excellent",
    "खराब": "bad", "बुरा": "bad", "बुरी": "bad", "घटिया": "poor", "बेकार": "useless", "कमज़ोर": "weak",
    "कमजोर": "weak", "कम": "less poor", "नहीं": "not", "नही": "not", "लेकिन": "but", "मगर": "but",
    "परंतु": "but", "और": "and", "है": "is", "हैं": "are", "था": "was", "थी": "was",
    "लैब": "lab", "प्रयोगशाला": "laboratory", "कंप्यूटर": "computers", "कम्प्यूटर": "computers",
    "उपकरण": "equipment", "सुविधा": "facilities", "सुविधाएं": "facilities", "सुविधाएँ": "facilities",
    "कक्षा": "classroom", "कमरा": "room", "पाठ्यक्रम": "syllabus", "सिलेबस": "syllabus", "विषय": "subject",
    "सामग्री": "material", "कठिन": "difficult", "मुश्किल": "difficult", "आसान": "easy", "सरल": "easy",
    "इंटरनेट": "internet", "वाईफाई": "wifi", "वाई-फाई": "wifi", "नेटवर्क": "network", "धीमा": "slow",
    "धीमी": "slow", "धीमे": "slow", "तेज़": "fast", "तेज": "fast", "गति": "speed", "स्पीड": "speed",
    "उपलब्ध": "available", "चलता": "works", "चलती": "works", "काम": "work", "समस्या": "problem",
    "परेशानी": "problem", "दिक्कत": "problem", "देरी": "delay", "सुधार": "improve", "ज़रूरत": "need",
    "जरूरत": "need", "आवश्यकता": "need", "संतुष्ट": "satisfied", "असंतुष्ट": "dissatisfied", "खुश": "happy",
    "पुराना": "old", "पुराने": "old", "टूटा": "broken", "टूटे": "broken", "साफ": "clean", "गंदा": "dirty",
    "गंदी": "dirty", "व्यावहारिक": "practical", "प्रैक्टिकल": "practical", "पुस्तकालय": "library",
}

NATIVE_TO_ENGLISH = {**TAMIL_TO_ENGLISH, **HINDI_TO_ENGLISH}

# Common ASCII emoticons/emoji -> sentiment words (students use them a lot)
EMOJI_MAP = {
    "😊": " good ", "😀": " good ", "😍": " excellent ", "👍": " good ", "❤": " excellent ", "😡": " bad ",
    "😞": " bad ", "😢": " bad ", "👎": " bad ", "😠": " bad ", "😐": " ", "🙁": " bad ",
}


def normalize_romanized_token(tok: str) -> str:
    """Collapse repeated letters (soooo -> soo) and map spelling variants."""
    import re
    t = re.sub(r"(.)\1{2,}", r"\1\1", tok.lower())
    return ROMAN_SPELLING_VARIANTS.get(t, t)


# ---------------------------------------------------------------------------
# Additional vocabulary (appended): more Romanized words, phrase rules,
# polarity lexicons and connectors.
# ---------------------------------------------------------------------------
ROMAN_TO_ENGLISH.update({
    "paravala": "okay", "paravalla": "okay", "paravaillai": "okay", "thaak": "okay", "thak": "okay",
    "periya": "big", "pazhaya": "old", "pazhaiya": "old", "adikkadi": "often", "puriyuthu": "understand",
    "puriyudhu": "understand", "purigiradhu": "understand", "kaam": "work", "kar": "do",
    "badi": "big", "bada": "big", "purana": "old", "purane": "old", "kam": "less poor",
    "bohot": "very", "ekdam": "completely", "poora": "completely", "pura": "completely",
    "periyadhu": "big", "sirithu": "small", "konjam": "little", "chinna": "small", "romba": "very",
    "payanulla": "useful", "payanulladhu": "useful", "useful": "useful", "kastam": "difficult",
    "theliva": "clear", "puriyala": "not understand", "illa": "not available",
    "ellarum": "everyone", "ellaarukkum": "everyone", "mathiri": "like", "slow": "slow",
})
ROMAN_TO_ENGLISH["accha"] = "good"
ROMAN_TO_ENGLISH["kharab"] = "bad"

TAMIL_TO_ENGLISH.update({
    "பிரச்சனையாக": "problem", "மிகப்பெரிய": "big", "பெரிய": "big", "பழையதாக": "old", "பழைய": "old",
    "பழுதடைந்துள்ளன": "broken", "பழுது": "broken", "போதுமானதாக": "enough", "போதுமான": "enough",
    "சாதாரணமாக": "average", "சாதாரண": "average", "சுமாராக": "average", "சுமார்": "average",
    "பரவாயில்லை": "okay", "ஓரளவு": "somewhat", "மெதுவாக": "slow", "அடிக்கடி": "often",
    "துண்டிக்கப்படுகிறது": "disconnect", "துண்டிக்கப்படுகின்றன": "disconnect", "பயனற்றதாக": "useless",
    "பயனுள்ளதாக": "useful", "திருப்தியாக": "satisfied", "காலாவதியாக": "outdated", "கடினமாக": "difficult",
    "முற்றிலும்": "completely", "புரியவில்லை": "not understand", "சரியாக": "properly", "புரிகிறது": "understand",
    "மோசமாக": "bad", "அருமையாக": "excellent", "சிறப்பாக": "excellent", "செய்யவில்லை": "not working",
    "இல்லை": "not available", "உள்ளது": "is", "குறைவாக": "less poor",
})

HINDI_TO_ENGLISH.update({
    "बड़ी": "big", "बड़ा": "big", "बिल्कुल": "completely", "बिलकुल": "completely", "पर्याप्त": "enough",
    "ठीक-ठाक": "okay", "ठीक": "okay", "सामान्य": "average", "औसत": "average", "संतोषजनक": "satisfied",
    "उपयोगी": "useful", "डिस्कनेक्ट": "disconnect", "बार-बार": "often", "बार": "often", "समझ": "understand",
    "खराब": "bad", "कठिन": "difficult", "पुराना": "old", "बुरा": "bad", "न": "not",
    "आता": "", "करता": "", "करती": "", "हो": "", "जाता": "", "जाती": "",
})
NATIVE_TO_ENGLISH.update(TAMIL_TO_ENGLISH)
NATIVE_TO_ENGLISH.update(HINDI_TO_ENGLISH)

# Multi-token phrase rules (applied on normalised tokens, longest match first).
PHRASES = {
    ("nalla", "illa"): "not good", ("accha", "nahi"): "not good", ("theek", "nahi"): "not good",
    ("sahi", "nahi"): "not good", ("kaam", "nahi"): "not working", ("work", "nahi"): "not working",
    ("work", "agala"): "not working", ("work", "agudhu"): "not working", ("work", "aaguthu"): "not working",
    ("enough", "illa"): "not enough", ("clear", "illa"): "not clear", ("puriyala",): "not understand",
    ("bahut", "kam"): "very poor", ("romba", "kammi"): "very poor", ("bahut", "kharab"): "very bad",
    ("अच्छा", "नहीं"): "not good", ("अच्छी", "नहीं"): "not good", ("अच्छे", "नहीं"): "not good",
    ("ठीक", "नहीं"): "not good", ("काम", "नहीं"): "not working", ("समझ", "नहीं"): "not understand",
    ("पर्याप्त", "नहीं"): "not enough", ("चलता", "नहीं"): "not working", ("चलती", "नहीं"): "not working",
    ("बहुत", "कम"): "very poor",
    ("வேலை", "செய்யவில்லை"): "not working", ("சரியாக", "இல்லை"): "not good",
    ("நன்றாக", "இல்லை"): "not good", ("போதுமானதாக", "இல்லை"): "not enough",
    ("போதுமான", "இல்லை"): "not enough", ("மிகவும்", "குறைவாக"): "very poor",
    ("not", "working"): "not working", ("not", "good"): "not good",
}

ENGLISH_CONTRACTIONS = {
    "cant": "can not", "dont": "do not", "isnt": "is not", "doesnt": "does not", "wont": "will not",
    "arent": "are not", "wasnt": "was not", "didnt": "did not", "couldnt": "could not", "havent": "have not",
    "hasnt": "has not", "shouldnt": "should not",
}

# Native-script suffixes stripped when a Tamil word is not found in the lexicon.
TAMIL_SUFFIXES = ["யாக", "ாக", "ாகவும்", "ங்களில்", "ங்களின்", "ங்கள்", "களின்", "களில்", "கள்", "ின்",
                  "த்தில்", "த்தை", "ையும்", "ும்", "ை", "ில்", "ால்", "ுடன்"]

# Polarity lexicons on the shared English "concept" space (used for the lexicon fallback,
# for the clause-split decision in ABSA, and for severity detection).
POSITIVE_WORDS = {
    "good", "great", "excellent", "amazing", "awesome", "wonderful", "helpful", "clear", "useful", "fast",
    "best", "nice", "perfect", "satisfied", "happy", "love", "like", "easy", "well", "better", "super",
    "relevant", "modern", "reliable", "smooth", "interesting", "informative", "supportive", "friendly",
    "outstanding", "fantastic", "brilliant", "maintained", "structured", "improved", "clean", "available",
}
NEGATIVE_WORDS = {
    "bad", "poor", "worst", "terrible", "awful", "horrible", "useless", "waste", "slow", "boring", "difficult",
    "outdated", "old", "broken", "problem", "problems", "issue", "issues", "dislike", "dirty", "unavailable",
    "disconnect", "disconnects", "disconnecting", "delay", "lag", "laggy", "weak", "dissatisfied", "unclear",
    "confusing", "insufficient", "irrelevant", "pathetic", "crowded", "noisy", "late", "lacking", "hard",
    "fast-paced", "overloaded", "unhelpful", "rude", "unusable", "faulty", "stuck", "complaint",
}
NEUTRAL_WORDS = {"average", "okay", "ok", "fine", "normal", "moderate", "decent", "somewhat", "so-so", "acceptable"}
NEGATORS = {"not", "no", "never", "cannot", "without", "neither", "nor", "none"}
INTENSIFIERS = {"very", "extremely", "really", "too", "so", "completely", "totally", "absolutely", "highly",
                "worst", "terrible", "horrible", "awful"}

HARD_CONNECTORS = {"but", "however", "although", "though", "yet", "ஆனால்", "लेकिन", "मगर", "परंतु", "किन्तु",
                   "aana", "aanaa", "aanal", "ana", "lekin", "magar", "parantu"}
SOFT_CONNECTORS = {"and", "aur", "और", "மற்றும்", "while", "also", "&", "plus", "பின்னர்", "तथा"}
HARD_PUNCT = {".", "!", "?", ";", "।", "\n"}
SOFT_PUNCT = {","}


# ---------------------------------------------------------------------------
# v2: hostel / campus vocabulary (Tamil, Hindi, Romanized) mapped to English concepts.
# ---------------------------------------------------------------------------
TAMIL_TO_ENGLISH.update({
    "விடுதி": "hostel", "விடுதியில்": "hostel", "விடுதிகள்": "hostel", "மெஸ்": "mess", "உணவு": "food",
    "உணவின்": "food", "சாப்பாடு": "food", "சாப்பாட்டு": "food", "சுவை": "taste", "தண்ணீர்": "water",
    "நீர்": "water", "மின்சாரம்": "electricity", "மின்": "electricity", "அறை": "room", "அறைகள்": "room",
    "சுத்தம்": "cleanliness", "சுகாதாரம்": "hygiene", "பாதுகாப்பு": "security", "பராமரிப்பு": "maintenance",
    "பேருந்து": "bus", "பஸ்": "bus", "போக்குவரத்து": "transport", "நூலகம்": "library", "விளையாட்டு": "sports",
    "மைதானம்": "ground", "நிகழ்ச்சி": "event", "நிகழ்வுகள்": "events", "நிர்வாகம்": "administration",
    "அலுவலகம்": "office", "கட்டணம்": "fees", "தேர்வு": "exam", "தேர்வுகள்": "exams", "மதிப்பெண்": "marks",
    "பணிகள்": "assignments", "வீட்டுப்பாடம்": "homework", "சந்தேகங்கள்": "doubts", "தாமதமாக": "late",
    "லேட்": "late", "எப்போதும்": "always", "கல்லூரி": "college", "வளாகம்": "campus", "கழிவறை": "toilet",
    "குளியலறை": "bathroom", "வாடன்": "warden", "காவலர்": "guard", "திருட்டு": "theft",
})
HINDI_TO_ENGLISH.update({
    "होस्टल": "hostel", "छात्रावास": "hostel", "हॉस्टल": "hostel", "मेस": "mess", "खाना": "food", "भोजन": "food",
    "खाने": "food", "स्वाद": "taste", "पानी": "water", "बिजली": "electricity", "कमरा": "room", "कमरे": "room",
    "सफाई": "cleanliness", "स्वच्छता": "hygiene", "सुरक्षा": "security", "रखरखाव": "maintenance",
    "बस": "bus", "परिवहन": "transport", "पुस्तकालय": "library", "लाइब्रेरी": "library", "खेल": "sports",
    "मैदान": "ground", "कार्यक्रम": "event", "प्रशासन": "administration", "कार्यालय": "office", "फीस": "fees",
    "परीक्षा": "exam", "परीक्षाएं": "exams", "अंक": "marks", "असाइनमेंट": "assignments", "संदेह": "doubts",
    "लेट": "late", "देर": "late", "हमेशा": "always", "कॉलेज": "college", "परिसर": "campus", "शौचालय": "toilet",
    "बाथरूम": "bathroom", "गार्ड": "guard", "चोरी": "theft",
})
NATIVE_TO_ENGLISH.update(TAMIL_TO_ENGLISH)
NATIVE_TO_ENGLISH.update(HINDI_TO_ENGLISH)
ROMAN_TO_ENGLISH.update({
    "saapadu": "food", "sapadu": "food", "sappadu": "food", "unavu": "food", "khana": "food", "khaana": "food",
    "thanni": "water", "tanni": "water", "paani": "water", "pani": "water", "bijli": "electricity",
    "current": "electricity", "arai": "room", "kamra": "room", "kamre": "room", "suthamilla": "dirty",
    "saaf": "clean", "gandagi": "dirty", "bus": "bus", "late": "late", "lateah": "late", "dhaan": "only",
    "hamesha": "always", "eppavum": "always", "sports": "sports", "mess": "mess", "hostel": "hostel",
    "pariksha": "exam", "kharaab": "bad", "kharab": "bad", "dikkat": "problem", "pareshani": "problem",
})
TANGLISH_MARKERS.update({"saapadu", "sapadu", "sappadu", "unavu", "thanni", "tanni", "suthamilla", "eppavum", "arai"})
HINGLISH_MARKERS.update({"khana", "khaana", "paani", "bijli", "hamesha", "dikkat", "pareshani", "gandagi", "saaf"})
NEGATIVE_WORDS.update({"late", "delayed", "tasteless", "dirty", "unhygienic", "unsafe", "cold", "stale", "overpriced",
                       "insufficient", "irregular", "unreliable", "disorganised", "disorganized", "unfair", "stressful",
                       "smelly", "leaking", "leak", "cut", "shortage", "scarcity", "noisy", "rude", "bad", "worse"})
POSITIVE_WORDS.update({"tasty", "delicious", "hygienic", "safe", "punctual", "organised", "organized", "fair",
                       "supportive", "comfortable", "spacious", "regular", "prompt", "cooperative", "enjoyable"})
PHRASES.update({
    ("power", "cut"): "power cut", ("power", "cuts"): "power cut", ("current", "illa"): "power cut",
    ("bijli", "nahi"): "power cut", ("மின்சாரம்", "இல்லை"): "power cut", ("बिजली", "नहीं"): "power cut",
    ("thanni", "illa"): "water shortage", ("paani", "nahi"): "water shortage", ("தண்ணீர்", "இல்லை"): "water shortage",
    ("पानी", "नहीं"): "water shortage", ("no", "water"): "water shortage",
    ("always", "late"): "always late",
})

TAMIL_TO_ENGLISH.update({"வினாத்தாள்": "question paper", "வினாத்தாள்கள்": "question papers", "வசதி": "facilities",
                         "ஒப்படைப்பு": "submission", "காலக்கெடு": "deadline", "நிகழ்ச்சிகள்": "events"})
HINDI_TO_ENGLISH.update({"प्रश्नपत्र": "question paper", "प्रश्न-पत्र": "question paper", "समय-सीमा": "deadline"})
NATIVE_TO_ENGLISH.update(TAMIL_TO_ENGLISH)
NATIVE_TO_ENGLISH.update(HINDI_TO_ENGLISH)
