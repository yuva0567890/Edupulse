import joblib
from nlp.preprocessing import preprocess

model = joblib.load("models/saved/english_sentiment_backup.joblib")

texts = [
    "The hostel is dirty and the food is terrible",
    "The teaching is excellent and very helpful",
    "The classroom has tables and chairs",
    "I am very happy with the college facilities",
    "The lab equipment is broken and useless"
]

for text in texts:
    processed_text = preprocess(text)["model_text"]
    prediction = model.predict([processed_text])[0]
    print(f"{text} -> {prediction}")