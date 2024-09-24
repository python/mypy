questions = (
    "Who is the Prime minister of India?: ",
    "Who is the CM of UP?: ",
    "Which planet in soalar system is hottest?: ",
    "Which country host olympics of 2024?: ",
    "Who is the precident of USA?: ",
)

options = (
    ("A. Mahatma Gandhi", "B. Rahul Gandhi", "C.Narendra Modi", "D.Indira Gandhi"),
    ("A.Yogi Adityanath", "B. Akhilesh Yadav", "C. Kalyan Singh", "D. R.V Paswan"),
    ("A. Venus", "B. Saturn", "C. Mars", "D. Mercury"),
    ("A. Italy", "B. Rome", "C. India", "D. France")(
        "A. Trump", "B. Biden", "C. Clinton", "D. Modi"
    ),
)

answers = ("C", "A", "A", "D", "B")
guesses = []
score = 0
question_num = 0

for question in questions:
    print("----------------")
    print(question)
    for option in options[question_num]:
        print(option)
        guess = input("Enter(A, B, C, D): ").upper()
        guesses.append(guess)
        if guess == answers[question_num]:
            score += 1
            print("CORRECT!")

        else:
            print("INCORRECT!")
            print(f"{answers[question_num]} is the correct answer")
        question_num += 1
