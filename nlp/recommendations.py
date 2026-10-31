"""Rule-based action recommendations (English / Tamil / Hindi).

Mapping: (aspect, sentiment) -> action text. For HIGH / CRITICAL priority and recurring
issues an escalation sentence is appended.
"""

SENT_I18N = {
    "Positive": {"en": "Positive", "ta": "நேர்மறை", "hi": "सकारात्मक"},
    "Neutral": {"en": "Neutral", "ta": "நடுநிலை", "hi": "तटस्थ"},
    "Negative": {"en": "Negative", "ta": "எதிர்மறை", "hi": "नकारात्मक"},
}
ASPECT_I18N = {
    "Teaching": {"en": "Teaching", "ta": "கற்பித்தல்", "hi": "शिक्षण"},
    "Lab/Infrastructure": {"en": "Lab / Infrastructure", "ta": "ஆய்வகம் / கட்டமைப்பு", "hi": "लैब / इंफ्रास्ट्रक्चर"},
    "Course Content": {"en": "Course Content", "ta": "பாட உள்ளடக்கம்", "hi": "पाठ्य सामग्री"},
    "Wi-Fi": {"en": "Wi-Fi", "ta": "வைஃபை", "hi": "वाई-फाई"},
    "General": {"en": "General", "ta": "பொது", "hi": "सामान्य"},
}

RULES = {
    ("Teaching", "Negative"): {
        "en": "Review teaching delivery, explanation clarity, teaching pace and student support.",
        "ta": "கற்பிக்கும் முறை, விளக்கத்தின் தெளிவு, கற்பிக்கும் வேகம் மற்றும் மாணவர் ஆதரவை மதிப்பாய்வு செய்யவும்.",
        "hi": "शिक्षण पद्धति, समझाने की स्पष्टता, पढ़ाने की गति और छात्र सहायता की समीक्षा करें।"},
    ("Lab/Infrastructure", "Negative"): {
        "en": "Inspect laboratory equipment, maintenance, availability and infrastructure facilities.",
        "ta": "ஆய்வக உபகரணங்கள், பராமரிப்பு, கிடைக்கும் தன்மை மற்றும் கட்டமைப்பு வசதிகளை ஆய்வு செய்யவும்.",
        "hi": "लैब उपकरण, रखरखाव, उपलब्धता और इंफ्रास्ट्रक्चर सुविधाओं का निरीक्षण करें।"},
    ("Course Content", "Negative"): {
        "en": "Review syllabus coverage, learning materials, content difficulty and practical relevance.",
        "ta": "பாடத்திட்ட வரம்பு, கற்றல் பொருட்கள், உள்ளடக்க கடினத்தன்மை மற்றும் நடைமுறை பொருத்தத்தை மதிப்பாய்வு செய்யவும்.",
        "hi": "पाठ्यक्रम कवरेज, अध्ययन सामग्री, कठिनाई स्तर और व्यावहारिक प्रासंगिकता की समीक्षा करें।"},
    ("Wi-Fi", "Negative"): {
        "en": "Check network speed, access points, connectivity and internet availability.",
        "ta": "நெட்வொர்க் வேகம், அணுகல் புள்ளிகள், இணைப்பு மற்றும் இணைய கிடைக்கும் தன்மையை சரிபார்க்கவும்.",
        "hi": "नेटवर्क स्पीड, एक्सेस पॉइंट, कनेक्टिविटी और इंटरनेट उपलब्धता की जाँच करें।"},
    ("General", "Negative"): {
        "en": "Read the feedback manually and route it to the responsible department.",
        "ta": "கருத்தை நேரடியாக படித்து பொறுப்பான துறைக்கு அனுப்பவும்.",
        "hi": "फीडबैक को स्वयं पढ़ें और संबंधित विभाग को भेजें।"},
}
NEUTRAL = {
    "en": "Monitor this aspect; gather more specific feedback to find small improvements.",
    "ta": "இந்த அம்சத்தை கண்காணிக்கவும்; சிறிய மேம்பாடுகளுக்கு மேலும் குறிப்பிட்ட கருத்துகளைச் சேகரிக்கவும்.",
    "hi": "इस पहलू की निगरानी करें; छोटे सुधारों के लिए और विशिष्ट फीडबैक एकत्र करें।"}
POSITIVE = {
    "en": "No action needed. Keep up the good practice and share it with other departments.",
    "ta": "நடவடிக்கை தேவையில்லை. நல்ல நடைமுறையைத் தொடரவும்; பிற துறைகளுடன் பகிரவும்.",
    "hi": "कोई कार्रवाई आवश्यक नहीं। अच्छी प्रथा जारी रखें और अन्य विभागों के साथ साझा करें।"}
ESCALATION = {
    "en": "Escalate to the Head of Department / academic committee: this is a {level} priority issue and has been reported {n} times recently.",
    "ta": "துறைத்தலைவர் / கல்விக் குழுவிற்கு எடுத்துச் செல்லவும்: இது {level} முன்னுரிமை சிக்கல்; சமீபத்தில் {n} முறை பதிவாகியுள்ளது.",
    "hi": "विभागाध्यक्ष / शैक्षणिक समिति को सूचित करें: यह {level} प्राथमिकता की समस्या है और हाल ही में {n} बार दर्ज हुई है।"}
LEVEL_I18N = {
    "LOW": {"en": "LOW", "ta": "குறைவு", "hi": "कम"},
    "MEDIUM": {"en": "MEDIUM", "ta": "நடுத்தரம்", "hi": "मध्यम"},
    "HIGH": {"en": "HIGH", "ta": "அதிகம்", "hi": "उच्च"},
    "CRITICAL": {"en": "CRITICAL", "ta": "மிக முக்கியம்", "hi": "गंभीर"},
}


def recommend(aspect, sentiment, level="LOW", frequency=0, recurring_threshold=3):
    """Return {'en':..., 'ta':..., 'hi':..., 'escalate': bool}."""
    if sentiment == "Negative":
        base = RULES.get((aspect, "Negative"), RULES[("General", "Negative")])
    elif sentiment == "Positive":
        base = POSITIVE
    else:
        base = NEUTRAL
    out = dict(base)
    escalate = sentiment == "Negative" and level in ("HIGH", "CRITICAL") and frequency >= recurring_threshold
    if escalate:
        for lang in ("en", "ta", "hi"):
            out[lang] = out[lang] + " " + ESCALATION[lang].format(level=LEVEL_I18N[level][lang], n=frequency)
    out["escalate"] = escalate
    return out


# ---------------------------------------------------------------------------
# v2: Hostel / Others / extra Academics aspects (English / Tamil / Hindi)
# ---------------------------------------------------------------------------
def _a(en, ta, hi):
    return {"en": en, "ta": ta, "hi": hi}


ASPECT_I18N.update({
    "Exams": _a("Exams", "தேர்வுகள்", "परीक्षाएं"), "Assignments": _a("Assignments", "பணிகள்", "असाइनमेंट"),
    "Academic Support": _a("Academic Support", "கல்வி ஆதரவு", "शैक्षणिक सहायता"),
    "Food": _a("Food / Mess", "உணவு / மெஸ்", "खाना / मेस"), "Room": _a("Room", "அறை", "कमरा"),
    "Cleanliness": _a("Cleanliness", "சுத்தம்", "सफाई"), "Water": _a("Water", "தண்ணீர்", "पानी"),
    "Electricity": _a("Electricity", "மின்சாரம்", "बिजली"), "Security": _a("Security", "பாதுகாப்பு", "सुरक्षा"),
    "Maintenance": _a("Maintenance", "பராமரிப்பு", "रखरखाव"),
    "Hostel Facilities": _a("Hostel Facilities", "விடுதி வசதிகள்", "हॉस्टल सुविधाएं"),
    "Transport": _a("Transport", "போக்குவரத்து", "परिवहन"), "Library": _a("Library", "நூலகம்", "पुस्तकालय"),
    "Sports": _a("Sports", "விளையாட்டு", "खेल"), "Events": _a("Events", "நிகழ்வுகள்", "कार्यक्रम"),
    "Administration": _a("Administration", "நிர்வாகம்", "प्रशासन"),
    "Campus Facilities": _a("Campus Facilities", "வளாக வசதிகள்", "परिसर सुविधाएं"),
})
RULES.update({
    ("Exams", "Negative"): _a(
        "Review exam scheduling, question paper difficulty, evaluation turnaround and result transparency.",
        "தேர்வு அட்டவணை, வினாத்தாள் கடினம், மதிப்பீட்டு நேரம் மற்றும் முடிவுகளின் வெளிப்படைத்தன்மையை மதிப்பாய்வு செய்யவும்.",
        "परीक्षा समय-सारणी, प्रश्नपत्र की कठिनाई, मूल्यांकन में समय और परिणामों की पारदर्शिता की समीक्षा करें।"),
    ("Assignments", "Negative"): _a(
        "Review assignment workload, deadlines and feedback turnaround; coordinate deadlines across courses.",
        "பணிகளின் சுமை, காலக்கெடு மற்றும் மதிப்பீட்டு நேரத்தை மதிப்பாய்வு செய்யவும்; பாடங்களுக்கிடையே காலக்கெடுவை ஒருங்கிணைக்கவும்.",
        "असाइनमेंट का बोझ, समय-सीमा और फीडबैक में लगने वाले समय की समीक्षा करें; कोर्सों के बीच समय-सीमा का समन्वय करें।"),
    ("Academic Support", "Negative"): _a(
        "Strengthen doubt-clearing sessions, mentoring and remedial support for students.",
        "சந்தேகம் தீர்க்கும் அமர்வுகள், வழிகாட்டுதல் மற்றும் கூடுதல் வகுப்பு ஆதரவை வலுப்படுத்தவும்.",
        "डाउट-क्लियरिंग सत्र, मार्गदर्शन और रेमेडियल सहायता को मजबूत करें।"),
    ("Food", "Negative"): _a(
        "Inspect mess food quality, hygiene, menu variety and serving timings; meet the mess committee.",
        "மெஸ் உணவின் தரம், சுகாதாரம், உணவு வகைகள் மற்றும் பரிமாறும் நேரத்தை ஆய்வு செய்யவும்; மெஸ் குழுவைச் சந்திக்கவும்.",
        "मेस के खाने की गुणवत्ता, स्वच्छता, मेन्यू की विविधता और समय की जाँच करें; मेस समिति से मिलें।"),
    ("Room", "Negative"): _a(
        "Inspect hostel rooms for space, furniture, ventilation and allocation problems.",
        "விடுதி அறைகளின் இடவசதி, தளபாடங்கள், காற்றோட்டம் மற்றும் ஒதுக்கீட்டு சிக்கல்களை ஆய்வு செய்யவும்.",
        "हॉस्टल कमरों में जगह, फर्नीचर, वेंटिलेशन और आवंटन की समस्याओं की जाँच करें।"),
    ("Cleanliness", "Negative"): _a(
        "Increase cleaning frequency, inspect washrooms and waste disposal, and audit housekeeping staff.",
        "சுத்தம் செய்யும் அடிக்கடி அதிகரிக்கவும், கழிவறைகள் மற்றும் குப்பை அகற்றலை ஆய்வு செய்யவும்.",
        "सफाई की आवृत्ति बढ़ाएँ, वॉशरूम और कचरा निस्तारण की जाँच करें और हाउसकीपिंग की समीक्षा करें।"),
    ("Water", "Negative"): _a(
        "Check water supply, storage tanks, drinking water quality and hot water availability.",
        "தண்ணீர் விநியோகம், சேமிப்பு தொட்டிகள், குடிநீர் தரம் மற்றும் வெந்நீர் கிடைப்பதை சரிபார்க்கவும்.",
        "पानी की आपूर्ति, टंकियों, पीने के पानी की गुणवत्ता और गर्म पानी की उपलब्धता की जाँच करें।"),
    ("Electricity", "Negative"): _a(
        "Inspect wiring, power backup (inverter/generator), lights and frequent power cuts.",
        "மின் வயரிங், மின் காப்பு (இன்வெர்ட்டர்/ஜெனரேட்டர்), விளக்குகள் மற்றும் அடிக்கடி மின்வெட்டை ஆய்வு செய்யவும்.",
        "वायरिंग, पावर बैकअप (इन्वर्टर/जनरेटर), लाइट और बार-बार बिजली कटौती की जाँच करें।"),
    ("Security", "Negative"): _a(
        "Review hostel security: guards, CCTV coverage, entry logs and safety complaints. Treat as urgent.",
        "விடுதி பாதுகாப்பை மதிப்பாய்வு செய்யவும்: காவலர்கள், CCTV, நுழைவு பதிவுகள் மற்றும் புகார்கள். அவசரமாகக் கருதவும்.",
        "हॉस्टल सुरक्षा की समीक्षा करें: गार्ड, CCTV, एंट्री लॉग और सुरक्षा शिकायतें। इसे अत्यावश्यक मानें।"),
    ("Maintenance", "Negative"): _a(
        "Create maintenance tickets, repair leaks/fittings and set a repair turnaround time.",
        "பராமரிப்பு பணி சீட்டுகளை உருவாக்கி, கசிவு/உபகரண பழுதுகளை சரிசெய்து, பழுது நீக்க நேரத்தை நிர்ணயிக்கவும்.",
        "मेंटेनेंस टिकट बनाएँ, लीकेज/फिटिंग ठीक करें और मरम्मत की समय-सीमा तय करें।"),
    ("Hostel Facilities", "Negative"): _a(
        "Inspect hostel facilities and discuss the issues with the hostel warden.",
        "விடுதி வசதிகளை ஆய்வு செய்து, விடுதி காப்பாளருடன் சிக்கல்களை விவாதிக்கவும்.",
        "हॉस्टल सुविधाओं का निरीक्षण करें और वार्डन के साथ समस्याओं पर चर्चा करें।"),
    ("Transport", "Negative"): _a(
        "Review bus timings, routes, capacity and driver punctuality; publish a reliable schedule.",
        "பேருந்து நேரங்கள், வழித்தடங்கள், இருக்கை திறன் மற்றும் ஓட்டுநர் நேரந்தவறாமையை மதிப்பாய்வு செய்யவும்.",
        "बस का समय, रूट, क्षमता और ड्राइवर की समय-पाबंदी की समीक्षा करें; भरोसेमंद समय-सारणी जारी करें।"),
    ("Library", "Negative"): _a(
        "Review library book availability, opening hours, seating and digital resources.",
        "நூலக புத்தகங்கள் கிடைப்பது, திறந்திருக்கும் நேரம், இருக்கைகள் மற்றும் டிஜிட்டல் வளங்களை மதிப்பாய்வு செய்யவும்.",
        "लाइब्रेरी में पुस्तकों की उपलब्धता, समय, बैठने की व्यवस्था और डिजिटल संसाधनों की समीक्षा करें।"),
    ("Sports", "Negative"): _a(
        "Review sports equipment, ground condition and scheduling for student access.",
        "விளையாட்டு உபகரணங்கள், மைதான நிலை மற்றும் மாணவர் பயன்பாட்டு அட்டவணையை மதிப்பாய்வு செய்யவும்.",
        "खेल उपकरण, मैदान की स्थिति और छात्रों के लिए समय-सारणी की समीक्षा करें।"),
    ("Events", "Negative"): _a(
        "Review event planning, communication and student participation opportunities.",
        "நிகழ்வு திட்டமிடல், தகவல் தொடர்பு மற்றும் மாணவர் பங்கேற்பு வாய்ப்புகளை மதிப்பாய்வு செய்யவும்.",
        "कार्यक्रम की योजना, सूचना और छात्रों की भागीदारी के अवसरों की समीक्षा करें।"),
    ("Administration", "Negative"): _a(
        "Review office response times, fee/scholarship processes and student communication.",
        "அலுவலக பதில் நேரம், கட்டணம்/உதவித்தொகை செயல்முறைகள் மற்றும் மாணவர் தகவல் தொடர்பை மதிப்பாய்வு செய்யவும்.",
        "कार्यालय के उत्तर समय, फीस/स्कॉलरशिप प्रक्रिया और छात्र संवाद की समीक्षा करें।"),
    ("Campus Facilities", "Negative"): _a(
        "Inspect campus facilities (canteen, parking, roads) and assign the issue to the facilities team.",
        "வளாக வசதிகளை (கேன்டீன், வாகன நிறுத்தம், சாலைகள்) ஆய்வு செய்து, வசதிகள் குழுவிற்கு ஒதுக்கவும்.",
        "परिसर सुविधाओं (कैंटीन, पार्किंग, सड़कें) की जाँच करें और सुविधा टीम को सौंपें।"),
})
