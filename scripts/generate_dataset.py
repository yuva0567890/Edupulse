"""Generate the SYNTHETIC multilingual seed datasets used to train / demo EduPulse.

IMPORTANT: this data is generated from hand-written phrase templates in English, Tamil,
Hindi, Tanglish, Hinglish and code-mixed styles. It is NOT real college data. Metrics
computed on it are optimistic (templates repeat) and only demonstrate that the pipeline
works. Replace data/training_data.csv with real, human-labelled feedback for real use.

Outputs
  data/training_data.csv   text,language,sentiment,aspect,severity,level
  data/sample_feedback.csv demo submissions used by scripts/seed_database.py

Run:  python scripts/generate_dataset.py
"""
import csv
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ASPECTS = ["Teaching", "Lab/Infrastructure", "Course Content", "Wi-Fi"]

# ---------------------------------------------------------------- subjects
SUBJ = {
    "en": {
        "Teaching": ["The teaching", "The teacher's explanation", "The faculty", "The lecturer", "Our professors", "The teaching method"],
        "Lab/Infrastructure": ["The lab equipment", "The computer lab", "The laboratory facilities", "The classroom infrastructure", "The lab computers"],
        "Course Content": ["The syllabus", "The course content", "The learning material", "The subject content", "The course difficulty"],
        "Wi-Fi": ["The WiFi", "The internet connection", "The campus network", "The WiFi speed", "The internet"],
    },
    "ta": {
        "Teaching": ["கற்பித்தல்", "ஆசிரியர்களின் விளக்கம்", "ஆசிரியர்கள் கற்பிக்கும் முறை", "விரிவுரையாளர்களின் கற்பித்தல்"],
        "Lab/Infrastructure": ["லேப் வசதிகள்", "ஆய்வக உபகரணங்கள்", "கணினி ஆய்வகம்", "வகுப்பறை வசதிகள்"],
        "Course Content": ["பாடத்திட்டம்", "பாட உள்ளடக்கம்", "கற்றல் பொருட்கள்", "பாடங்களின் கடினத்தன்மை"],
        "Wi-Fi": ["வைஃபை", "இணைய இணைப்பு", "கல்லூரி நெட்வொர்க்", "இணைய வேகம்"],
    },
    "hi": {
        "Teaching": ["पढ़ाने का तरीका", "शिक्षकों की व्याख्या", "शिक्षण", "प्राध्यापकों का पढ़ाना"],
        "Lab/Infrastructure": ["लैब की सुविधा", "प्रयोगशाला के उपकरण", "कंप्यूटर लैब", "कक्षा की सुविधाएं"],
        "Course Content": ["पाठ्यक्रम", "विषय की सामग्री", "पढ़ाई की सामग्री", "कोर्स की कठिनाई"],
        "Wi-Fi": ["वाईफाई", "इंटरनेट कनेक्शन", "कॉलेज का नेटवर्क", "इंटरनेट की स्पीड"],
    },
    "tg": {  # Tanglish (Romanized Tamil + English nouns)
        "Teaching": ["teaching", "teacher explanation", "sir oda teaching", "faculty", "aasiriyar teaching style"],
        "Lab/Infrastructure": ["lab equipment", "computer lab", "lab facilities", "classroom vasathi", "lab computers"],
        "Course Content": ["syllabus", "course content", "study material", "subject content", "portion"],
        "Wi-Fi": ["wifi", "internet", "college network", "wifi speed"],
    },
    "hg": {  # Hinglish (Romanized Hindi)
        "Teaching": ["teaching", "teacher ki explanation", "padhane ka tarika", "faculty"],
        "Lab/Infrastructure": ["lab ke computers", "lab ki suvidha", "classroom ki suvidha", "lab equipment"],
        "Course Content": ["syllabus", "course content", "study material", "subject ka content"],
        "Wi-Fi": ["wifi", "internet", "college ka network", "wifi speed"],
    },
}
# subjects used for code-mixed styles (English noun phrase / Tamil / Hindi mixed)
SUBJ_MIX = {
    "Teaching": ["Teacher explanation", "Teaching", "Faculty teaching", "Lecturer"],
    "Lab/Infrastructure": ["Lab equipment", "Computer lab", "Lab facilities", "Classroom facilities"],
    "Course Content": ["Syllabus", "Course content", "Study material", "Subject content"],
    "Wi-Fi": ["WiFi", "Internet", "Campus network", "WiFi speed"],
}

# ------------------------------------------------------------ predicates
# (text, sentiment, severity)
P = "Positive"
N = "Neutral"
G = "Negative"
PRED = {
    "en": [
        ("is very good", P, "Low"), ("is excellent", P, "Low"), ("is really helpful and clear", P, "Low"),
        ("is great and I am satisfied", P, "Low"), ("is amazing", P, "Low"),
        ("is average", N, "Low"), ("is okay and nothing special", N, "Low"), ("is fine", N, "Low"),
        ("is neither good nor bad", N, "Low"), ("is decent", N, "Low"),
        ("is not that good", G, "Medium"), ("could be better", G, "Medium"), ("is lacking", G, "Medium"),
        ("is poor", G, "High"), ("is very bad", G, "High"), ("is terrible and needs improvement", G, "High"),
        ("is not good at all", G, "High"), ("is completely useless", G, "Critical"),
        ("is a major problem", G, "Critical"), ("is the worst and nothing works", G, "Critical"),
    ],
    "ta": [
        ("மிகவும் நன்றாக உள்ளது", P, "Low"), ("சிறப்பாக உள்ளது", P, "Low"), ("அருமையாக உள்ளது", P, "Low"),
        ("மிகவும் பயனுள்ளதாக உள்ளது", P, "Low"), ("திருப்தியாக உள்ளது", P, "Low"),
        ("சாதாரணமாக உள்ளது", N, "Low"), ("சுமாராக உள்ளது", N, "Low"), ("பரவாயில்லை", N, "Low"),
        ("ஓரளவு சரியாக உள்ளது", N, "Low"),
        ("சரியாக இல்லை", G, "Medium"), ("குறைவாக உள்ளது", G, "Medium"), ("போதுமானதாக இல்லை", G, "Medium"),
        ("மிகவும் மோசமாக உள்ளது", G, "High"), ("மோசமாக உள்ளது", G, "High"), ("பயனற்றதாக உள்ளது", G, "High"),
        ("முற்றிலும் வேலை செய்யவில்லை", G, "Critical"), ("மிகப்பெரிய பிரச்சனையாக உள்ளது", G, "Critical"),
    ],
    "hi": [
        ("बहुत अच्छा है", P, "Low"), ("बहुत बढ़िया है", P, "Low"), ("शानदार है", P, "Low"),
        ("बहुत उपयोगी है", P, "Low"), ("संतोषजनक है", P, "Low"),
        ("ठीक-ठाक है", N, "Low"), ("सामान्य है", N, "Low"), ("औसत है", N, "Low"), ("न अच्छा है न बुरा", N, "Low"),
        ("अच्छा नहीं है", G, "Medium"), ("बहुत कम है", G, "Medium"), ("पर्याप्त नहीं है", G, "Medium"),
        ("बहुत खराब है", G, "High"), ("बेकार है", G, "High"), ("घटिया है", G, "High"),
        ("बिल्कुल काम नहीं करता", G, "Critical"), ("बहुत बड़ी समस्या है", G, "Critical"),
    ],
    "tg": [
        ("romba nalla iruku", P, "Low"), ("semma iruku", P, "Low"), ("arumaiya iruku", P, "Low"),
        ("romba useful ah iruku", P, "Low"), ("super ah iruku", P, "Low"),
        ("okay okay iruku", N, "Low"), ("average ah iruku", N, "Low"), ("paravala", N, "Low"), ("normal ah iruku", N, "Low"),
        ("nalla illa", G, "Medium"), ("kammi ah iruku", G, "Medium"), ("enough illa", G, "Medium"),
        ("romba mosam", G, "High"), ("romba mokkai ah iruku", G, "High"), ("waste ah iruku", G, "High"),
        ("work agala", G, "Critical"), ("romba periya problem", G, "Critical"),
    ],
    "hg": [
        ("bahut accha hai", P, "Low"), ("bahut badhiya hai", P, "Low"), ("mast hai", P, "Low"),
        ("bahut useful hai", P, "Low"), ("sahi hai", P, "Low"),
        ("theek-thaak hai", N, "Low"), ("average hai", N, "Low"), ("normal hai", N, "Low"),
        ("accha nahi hai", G, "Medium"), ("bahut kam hai", G, "Medium"), ("enough nahi hai", G, "Medium"),
        ("bahut kharab hai", G, "High"), ("bekar hai", G, "High"), ("ganda hai", G, "High"),
        ("bilkul kaam nahi karta", G, "Critical"), ("bahut badi problem hai", G, "Critical"),
    ],
    # code-mixed predicates: native-script grammar with English adjectives
    "ta_en": [
        ("மிகவும் good ஆக உள்ளது", P, "Low"), ("super ஆக உள்ளது", P, "Low"), ("very helpful ஆக உள்ளது", P, "Low"),
        ("excellent ஆக உள்ளது", P, "Low"),
        ("average ஆக உள்ளது", N, "Low"), ("okay ஆக உள்ளது", N, "Low"), ("fine ஆக உள்ளது", N, "Low"),
        ("not good ஆக உள்ளது", G, "Medium"), ("மிகவும் poor ஆக உள்ளது", G, "High"),
        ("மிகவும் slow ஆக உள்ளது", G, "High"), ("terrible ஆக உள்ளது", G, "High"),
        ("not working ஆக உள்ளது", G, "Critical"), ("completely useless ஆக உள்ளது", G, "Critical"),
    ],
    "hi_en": [
        ("बहुत good है", P, "Low"), ("बहुत helpful है", P, "Low"), ("excellent है", P, "Low"),
        ("average है", N, "Low"), ("okay है", N, "Low"), ("fine है", N, "Low"),
        ("not good है", G, "Medium"), ("बहुत poor है", G, "High"), ("बहुत slow है", G, "High"),
        ("terrible है", G, "High"), ("बिल्कुल not working है", G, "Critical"), ("completely useless है", G, "Critical"),
    ],
}
# aspect specific predicates (more natural and informative)
ASPRED = {
    "en": {
        "Teaching": [("is clear and easy to understand", P, "Low"), ("is boring and too fast to follow", G, "High"),
                     ("is not clear and hard to understand", G, "High")],
        "Lab/Infrastructure": [("is well maintained and modern", P, "Low"), ("is outdated and not working", G, "Critical"),
                               ("is not enough for all students", G, "Medium")],
        "Course Content": [("is relevant and well structured", P, "Low"), ("is outdated and too difficult", G, "High"),
                           ("has no practical relevance", G, "High")],
        "Wi-Fi": [("is fast and reliable", P, "Low"), ("is very slow and keeps disconnecting", G, "High"),
                  ("is not working at all", G, "Critical"), ("is unavailable in the hostel", G, "High")],
    },
    "ta": {
        "Teaching": [("தெளிவாக புரிகிறது", P, "Low"), ("புரியவில்லை", G, "High")],
        "Lab/Infrastructure": [("போதுமானதாக இல்லை", G, "Medium"), ("பழையதாக உள்ளது", G, "High")],
        "Course Content": [("மிகவும் கடினமாக உள்ளது", G, "High"), ("காலாவதியாக உள்ளது", G, "High")],
        "Wi-Fi": [("மிகவும் மெதுவாக உள்ளது", G, "High"), ("அடிக்கடி துண்டிக்கப்படுகிறது", G, "High"),
                  ("வேலை செய்யவில்லை", G, "Critical")],
    },
    "hi": {
        "Teaching": [("समझ नहीं आता", G, "High"), ("बहुत अच्छे से समझाते हैं", P, "Low")],
        "Lab/Infrastructure": [("पर्याप्त नहीं है", G, "Medium"), ("पुराना है", G, "High")],
        "Course Content": [("बहुत कठिन है", G, "High"), ("पुराना है", G, "High")],
        "Wi-Fi": [("बहुत धीमा है", G, "High"), ("बार-बार डिस्कनेक्ट हो जाता है", G, "High"),
                  ("बिल्कुल काम नहीं करता", G, "Critical")],
    },
    "tg": {
        "Teaching": [("romba theliva puriyuthu", P, "Low"), ("puriyala", G, "High")],
        "Lab/Infrastructure": [("romba pazhaya mathiri iruku", G, "High"), ("equipment kidaikala", G, "Medium")],
        "Course Content": [("romba kastam", G, "High"), ("romba pazhaya portion", G, "High")],
        "Wi-Fi": [("romba slow ah iruku", G, "High"), ("adikkadi disconnect aagudhu", G, "High"), ("work agala", G, "Critical")],
    },
    "hg": {
        "Teaching": [("samajh nahi aata", G, "High")],
        "Lab/Infrastructure": [("purana hai", G, "High")],
        "Course Content": [("bahut kathin hai", G, "High")],
        "Wi-Fi": [("bahut slow hai", G, "High"), ("bahut dhima hai", G, "High")],
    },
}


# ---------------------------------------------------------------- v2: extra aspects (Hostel / Others / Academics)
EXTRA_ASPECTS = ["Exams", "Assignments", "Academic Support", "Food", "Room", "Cleanliness", "Water", "Electricity",
                 "Security", "Maintenance", "Transport", "Library", "Sports", "Events", "Administration", "Campus Facilities"]
EXTRA_SUBJ = {
    "en": {
        "Exams": ["The exam schedule", "The question papers", "The evaluation"],
        "Assignments": ["The assignments", "The assignment workload", "The submission deadlines"],
        "Academic Support": ["The doubt clearing sessions", "The academic support", "The mentoring"],
        "Food": ["The hostel food", "The mess food", "The food in the mess", "The hostel mess"],
        "Room": ["The hostel rooms", "My hostel room", "The room facilities"],
        "Cleanliness": ["The hostel cleanliness", "The hostel washrooms", "The hygiene in the hostel"],
        "Water": ["The water supply in the hostel", "The drinking water", "The hot water"],
        "Electricity": ["The electricity in the hostel", "The power supply", "The power backup"],
        "Security": ["The hostel security", "The security guards", "The safety in the hostel"],
        "Maintenance": ["The hostel maintenance", "The repair work", "The maintenance team"],
        "Transport": ["The college bus", "The bus service", "The transport facility"],
        "Library": ["The library", "The library books", "The library timings"],
        "Sports": ["The sports facilities", "The playground", "The gym"],
        "Events": ["The college events", "The cultural fest", "The workshops"],
        "Administration": ["The administration", "The office staff", "The fee payment process"],
        "Campus Facilities": ["The campus facilities", "The parking", "The campus canteen"],
    },
    "ta": {
        "Exams": ["தேர்வு அட்டவணை", "வினாத்தாள்கள்"], "Assignments": ["பணிகளின் சுமை", "ஒப்படைப்பு காலக்கெடு"],
        "Academic Support": ["சந்தேகம் தீர்க்கும் அமர்வுகள்"], "Food": ["விடுதி உணவு", "மெஸ் உணவு", "விடுதி சாப்பாடு"],
        "Room": ["விடுதி அறைகள்"], "Cleanliness": ["விடுதி சுத்தம்", "விடுதி கழிவறைகள்"],
        "Water": ["விடுதி தண்ணீர் வசதி", "குடிநீர்"], "Electricity": ["விடுதி மின்சாரம்"],
        "Security": ["விடுதி பாதுகாப்பு"], "Maintenance": ["விடுதி பராமரிப்பு"],
        "Transport": ["கல்லூரி பேருந்து", "பேருந்து சேவை"], "Library": ["நூலகம்"], "Sports": ["விளையாட்டு வசதிகள்", "மைதானம்"],
        "Events": ["கல்லூரி நிகழ்வுகள்"], "Administration": ["நிர்வாகம்", "அலுவலக ஊழியர்கள்"], "Campus Facilities": ["வளாக வசதிகள்"],
    },
    "hi": {
        "Exams": ["परीक्षा समय-सारणी", "प्रश्नपत्र"], "Assignments": ["असाइनमेंट का बोझ", "जमा करने की समय-सीमा"],
        "Academic Support": ["डाउट क्लियरिंग सत्र"], "Food": ["हॉस्टल का खाना", "मेस का खाना", "होस्टल का भोजन"],
        "Room": ["हॉस्टल के कमरे"], "Cleanliness": ["हॉस्टल की सफाई", "हॉस्टल के शौचालय"],
        "Water": ["हॉस्टल में पानी की सुविधा", "पीने का पानी"], "Electricity": ["हॉस्टल की बिजली"],
        "Security": ["हॉस्टल की सुरक्षा"], "Maintenance": ["हॉस्टल का रखरखाव"],
        "Transport": ["कॉलेज की बस", "बस सेवा"], "Library": ["पुस्तकालय"], "Sports": ["खेल की सुविधाएं", "मैदान"],
        "Events": ["कॉलेज के कार्यक्रम"], "Administration": ["प्रशासन", "कार्यालय के कर्मचारी"], "Campus Facilities": ["परिसर की सुविधाएं"],
    },
    "tg": {
        "Exams": ["exam schedule", "question paper"], "Assignments": ["assignment workload", "submission deadline"],
        "Academic Support": ["doubt clearing session"], "Food": ["hostel saapadu", "mess food", "hostel food"],
        "Room": ["hostel room"], "Cleanliness": ["hostel cleanliness", "hostel washroom"],
        "Water": ["hostel thanni", "drinking water"], "Electricity": ["hostel current", "power supply"],
        "Security": ["hostel security"], "Maintenance": ["hostel maintenance"],
        "Transport": ["college bus", "bus service"], "Library": ["library"], "Sports": ["sports facility", "playground"],
        "Events": ["college events"], "Administration": ["administration", "office staff"], "Campus Facilities": ["campus facilities", "parking"],
    },
    "hg": {
        "Exams": ["exam schedule", "question paper"], "Assignments": ["assignment ka load"],
        "Academic Support": ["doubt clearing session"], "Food": ["hostel ka khana", "mess ka khana"],
        "Room": ["hostel ke room"], "Cleanliness": ["hostel ki safai"], "Water": ["hostel mein paani", "drinking water"],
        "Electricity": ["hostel ki bijli"], "Security": ["hostel ki security"], "Maintenance": ["hostel maintenance"],
        "Transport": ["college bus", "bus service"], "Library": ["library"], "Sports": ["sports facilities"],
        "Events": ["college events"], "Administration": ["administration", "office staff"], "Campus Facilities": ["campus facilities"],
    },
}
for _st, _d in EXTRA_SUBJ.items():
    for _a, _v in _d.items():
        SUBJ[_st][_a] = _v
for _a in EXTRA_ASPECTS:
    SUBJ_MIX[_a] = EXTRA_SUBJ["en"][_a]
ASPRED["en"].update({
    "Food": [("is tasteless and cold", G, "High"), ("is tasty and well cooked", P, "Low"), ("is unhygienic", G, "High")],
    "Transport": [("is always late", G, "Medium"), ("is punctual", P, "Low"), ("is overcrowded", G, "High")],
    "Water": [("is not available", G, "Critical"), ("is regular and clean", P, "Low")],
    "Electricity": [("has frequent power cuts", G, "High"), ("is reliable", P, "Low")],
    "Security": [("is not safe at night", G, "Critical"), ("is strict and good", P, "Low")],
    "Cleanliness": [("is very dirty", G, "High"), ("is clean and tidy", P, "Low")],
    "Exams": [("is well organised", P, "Low"), ("is too difficult and unfair", G, "High")],
})
ALL_ASPECTS = ASPECTS + EXTRA_ASPECTS

LANG_LABEL = {"en": "English", "ta": "Tamil", "hi": "Hindi", "tg": "Tanglish", "hg": "Hinglish",
              "ta_en": "Tamil + English", "hi_en": "Hindi + English"}
CONNECT = {"en": ["but", "and", "while"], "ta": ["ஆனால்", "மற்றும்"], "hi": ["लेकिन", "और"],
           "tg": ["but", "aana", "and"], "hg": ["lekin", "aur"], "ta_en": ["but", "ஆனால்"], "hi_en": ["but", "लेकिन"]}
SEV_ORDER = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}


def category_of(aspect):
    from nlp.categories import ASPECT_CATEGORY
    return ASPECT_CATEGORY.get(aspect, "Others")


def subjects_for(style, aspect):
    if style in SUBJ:
        return SUBJ[style][aspect]
    if style == "ta_en":
        return SUBJ_MIX[aspect] + SUBJ["ta"][aspect][:2]
    return SUBJ_MIX[aspect] + SUBJ["hi"][aspect][:2]


def preds_for(style, aspect):
    base = PRED[style]
    extra = ASPRED.get(style, {}).get(aspect, [])
    if style in ("ta_en", "hi_en"):
        extra = []
    return base + extra


def make_clause(style, aspect, sentiment, rng):
    cands = [p for p in preds_for(style, aspect) if p[1] == sentiment]
    pred = rng.choice(cands)
    subj = rng.choice(subjects_for(style, aspect))
    # wifi/lab "romba slow" style predicates only sensible for some aspects - good enough for a demo set
    return f"{subj} {pred[0]}", pred[2]


def lang_of_pair(a, b):
    if a == b:
        return LANG_LABEL[a]
    s = {a, b}
    if s <= {"en", "tg", "ta_en"}:
        return "Tanglish" if "tg" in s else "Tamil + English"
    if s <= {"en", "hg", "hi_en"}:
        return "Hinglish" if "hg" in s else "Hindi + English"
    return "Mixed"


def build_training(rng):
    rows, seen = [], set()
    styles = list(LANG_LABEL)
    # clause level
    for style in styles:
        for aspect in ALL_ASPECTS:
            for sent in (P, N, G):
                for _ in range(10 if aspect in ASPECTS else 5):
                    text, sev = make_clause(style, aspect, sent, rng)
                    if text in seen:
                        continue
                    seen.add(text)
                    rows.append([text, LANG_LABEL[style], sent, aspect, sev, "clause", category_of(aspect)])
    # lexicon-vocabulary rows (weak supervision so common opinion words outside the templates are known)
    from nlp import multilingual_utils as mu
    for words, sent, sev in ((sorted(mu.POSITIVE_WORDS), P, "Low"), (sorted(mu.NEGATIVE_WORDS), G, "High"),
                             (sorted(mu.NEUTRAL_WORDS), N, "Low")):
        for w in words:
            aspect = rng.choice(ASPECTS)
            subj = rng.choice(SUBJ["en"][aspect])
            frm = rng.choice(["{s} is {w}", "{s} was {w}", "{s} is really {w}", "{s} seems {w}"])
            text = frm.format(s=subj, w=w)
            if text not in seen:
                seen.add(text)
                rows.append([text, "English", sent, aspect, sev, "clause", category_of(aspect)])
    # full (two aspect) feedback
    n_full = 0
    while n_full < 1400:
        sa = rng.choice(styles)
        sb = sa if rng.random() < 0.75 else rng.choice(styles)
        a1 = rng.choice(ALL_ASPECTS)
        a2 = rng.choice([a for a in ALL_ASPECTS if a != a1])
        s1, s2 = rng.choice([P, N, G]), rng.choice([P, N, G])
        t1, v1 = make_clause(sa, a1, s1, rng)
        t2, v2 = make_clause(sb, a2, s2, rng)
        conn = rng.choice(CONNECT[sa])
        text = f"{t1} {conn} {t2}"
        if rng.random() < 0.3:
            text += "."
        if text in seen:
            continue
        seen.add(text)
        if G in (s1, s2):
            overall = G
        elif P in (s1, s2):
            overall = P
        else:
            overall = N
        sev = max(v1 if s1 == G else "Low", v2 if s2 == G else "Low", key=lambda x: SEV_ORDER[x])
        rows.append([text, lang_of_pair(sa, sb), overall, "|".join([a1, a2]), sev, "full", category_of(a1)])
        n_full += 1
    rng.shuffle(rows)
    return rows


# --------------------------------------------------------------------- sample feedback
DEPTS = ["Computer Science", "Information Technology", "Electronics", "Mechanical", "Civil", "Management Studies"]
COURSES = {
    "Computer Science": ["Data Structures", "Operating Systems", "Machine Learning", "DBMS"],
    "Information Technology": ["Web Technology", "Computer Networks", "Cloud Computing"],
    "Electronics": ["Digital Electronics", "Signals and Systems", "Embedded Systems"],
    "Mechanical": ["Thermodynamics", "Fluid Mechanics", "CAD/CAM"],
    "Civil": ["Surveying", "Structural Analysis", "Concrete Technology"],
    "Management Studies": ["Marketing", "Finance", "Operations"],
}
NAMES = ["Arun", "Priya", "Karthik", "Divya", "Rahul", "Anita", "Mohan", "Sneha", "Vikram", "Meena", "Suresh", "Pooja"]

HAND_WRITTEN = [
    ("English", "The teaching is very clear and the lab facilities are good.", 5),
    ("Tamil", "ஆசிரியர் நன்றாக கற்பிக்கிறார் ஆனால் லேப் வசதிகள் குறைவாக உள்ளது.", 3),
    ("Hindi", "शिक्षक बहुत अच्छा पढ़ाते हैं लेकिन लैब की सुविधा अच्छी नहीं है।", 3),
    ("Tanglish", "Teaching romba nalla iruku but lab equipment illa.", 3),
    ("Tamil + English", "Teacher explanation super but WiFi romba slow.", 3),
    ("Hindi + English", "Teacher explanation अच्छा है but WiFi बहुत slow है.", 3),
    ("Hindi + English", "लैब में कंप्यूटर बहुत slow हैं।", 2),
    ("English", "Teaching is very good and explanations are clear.", 5),
    ("Tamil", "ஆசிரியர் நன்றாக கற்பிக்கிறார்.", 5),
    ("English", "The WiFi keeps disconnecting and is not working in the library at all.", 1),
    ("English", "Syllabus is outdated and has no practical relevance.", 2),
    ("Tanglish", "Syllabus romba kastam, portion romba pazhaya mathiri iruku.", 2),
    ("Hindi", "वाईफाई बिल्कुल काम नहीं करता, बहुत बड़ी समस्या है।", 1),
    ("Tamil", "வைஃபை மிகவும் மெதுவாக உள்ளது மற்றும் அடிக்கடி துண்டிக்கப்படுகிறது.", 2),
    ("English", "The course content is okay and the teaching is average.", 3),
]


def build_samples(rng, train_rows, n=300):
    """Sample feedback with timestamps (days_ago), recurring Wi-Fi and lab problems included."""
    full = [r for r in train_rows if r[5] == "full"]
    clause = [r for r in train_rows if r[5] == "clause"]
    out = []
    # recurring wifi complaints so priority + recurring-issue charts have signal
    wifi_neg = [r for r in clause if r[3] == "Wi-Fi" and r[2] == G]
    lab_neg = [r for r in clause if r[3] == "Lab/Infrastructure" and r[2] == G]
    pool = []
    pool += [(r[0], r[1]) for r in rng.sample(wifi_neg, min(40, len(wifi_neg)))]
    pool += [(r[0], r[1]) for r in rng.sample(lab_neg, min(24, len(lab_neg)))]
    pool += [(r[0], r[1]) for r in rng.sample(full, min(150, len(full)))]
    pool += [(r[0], r[1]) for r in rng.sample(clause, min(60, len(clause)))]
    for cat, k in (("Hostel", 45), ("Others", 25)):
        cs = [r for r in clause if r[6] == cat and r[2] == G]
        pool += [(r[0], r[1]) for r in rng.sample(cs, min(k, len(cs)))]
    pool += [(t, l) for l, t, _ in HAND_WRITTEN]
    rng.shuffle(pool)
    for text, lang in pool[:n + 60]:
        dept = rng.choice(DEPTS)
        out.append({
            "days_ago": rng.randint(0, 59), "student_name": rng.choice(NAMES) if rng.random() < 0.6 else "",
            "student_id": f"S{rng.randint(1000, 9999)}" if rng.random() < 0.6 else "",
            "department": dept, "year": rng.choice(["1", "2", "3", "4"]), "course": rng.choice(COURSES[dept]),
            "language_hint": "Auto Detect", "feedback_text": text, "rating": rng.choice(["", "1", "2", "3", "4", "5"]),
        })
    return out


def main():
    rng = random.Random(42)
    rows = build_training(rng)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    p = os.path.join(ROOT, "data", "training_data.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "language", "sentiment", "aspect", "severity", "level", "category"])
        w.writerows(rows)
    samples = build_samples(random.Random(7), rows)
    p2 = os.path.join(ROOT, "data", "sample_feedback.csv")
    with open(p2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(samples[0].keys()))
        w.writeheader()
        w.writerows(samples)
    print(f"Wrote {len(rows)} training rows -> {p}")
    print(f"Wrote {len(samples)} sample feedback rows -> {p2}")


if __name__ == "__main__":
    sys.exit(main())
