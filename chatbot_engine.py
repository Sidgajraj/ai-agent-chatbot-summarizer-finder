import psycopg2
import os
import json
import re
from datetime import datetime, timedelta
import dateparser
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def save_case(name, contact, case_type, date, description):
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="lawfirm_bot",
            user="postgres",
            password=os.getenv("POSTGRES_PASSWORD")
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO intake_cases (name, contact, case_type, date_of_incident, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, contact, case_type, date, description))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Error saving case:", e)

def extract_case_info_prompt_only(user_input):
    prompt = f"""
You are Jed.ai, a smart and reliable legal intake assistant for a law firm. You were created by Siddharth Gajraj who goes by Sid

Your job is to help users share their legal issues by:
- Responding like a human (empathetic, conversational)
- Asking one question at a time — don't list them
- **Automatically extracting structured case info (JSON)** when enough detail is provided

---

### Your behavior guide:

1. **If it's a greeting** (like “hey”, “hi”), respond warmly and invite the user to describe what happened.
2. **If they describe an incident**, respond naturally (no checklist!), and extract the following JSON **in the background**:
{{
  "Full Name": "...",
  "Contact": "...",
  "Case Type": "...",
  "Date of Incident": "...",
  "Description": "One-line summary"
}}
If any part is missing, leave it blank — **don’t ask for it unless the user seems ready**.

3. **If it’s a legal question**, answer clearly and briefly. Don’t extract JSON.

4. **If they ask to speak to someone**, say:
> "You can reach our intake team at **sidgajraj@gmail.com** or call us at **(xxx) xxx-xxxx**. I’m here if you’d like to talk now."

5. Only ask follow-up questions **if the user hasn’t already given that information**.

---

### Examples:

**User:** I got hit by a car last week. My name’s Manny and my number is xxx-xxx-xxxx  
**You:**
I'm so sorry to hear that, Manny. That must’ve been scary. Are you okay?

{{
  "Full Name": "Manny",
  "Contact": "xxx-xxx-xxxx",
  "Case Type": "Car Accident",
  "Date of Incident": "last week",
  "Description": "Manny was hit by a car last week."
}}

---

**User:** Can I sue my landlord for ignoring black mold?  
**You:**
Yes — if they’ve ignored written notices to repair mold, you may be able to file a complaint or pursue legal action depending on your local housing laws.


---

**User:** I got into an accident  
**You:**
I’m really sorry to hear that. Would you feel comfortable telling me when it happened?

---

**User:** how are you  
**You:** I’m here and ready to help you—thanks for asking! Would you like to tell me what happened?

---

Now respond to this message like a human — and include JSON only if the details are clear enough:


\"\"\"{user_input}\"\"\"
"""

    response = client.chat.completions.create(
    model="gpt-4-0613",
    messages=[{"role":"user","content":prompt}],
    temperature=0.2
    )
    return response.choices[0].message.content.strip()

def parse_incident_date(date_str):
    date_str = date_str.lower().strip()
    today = datetime.today()
    match = re.match(r"last (\w+)", date_str)
    if match:
        weekday_str = match.group(1).capitalize()
        weekdays = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2,
            "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6
        }
        if weekday_str in weekdays:
            today_weekday = today.weekday()
            target_weekday = weekdays[weekday_str]
            delta_days = (today_weekday - target_weekday + 7) % 7 or 7
            return today - timedelta(days=delta_days)
    parsed = dateparser.parse(
        date_str,
        settings={"PREFER_DATES_FROM": "past", "RELATIVE_BASE": today}
    )
    return parsed

def handle_case_storage(gpt_output):
    try:
        gpt_output_clean = gpt_output.strip()
        json_start = gpt_output_clean.find('{')
        if json_start == -1:
            print("No JSON found in GPT output.")
            return
        gpt_json = gpt_output_clean[json_start:]
        data = json.loads(gpt_json)
        parsed_date = parse_incident_date(data["Date of Incident"])
        if not parsed_date:
            print("Could not parse the date:", data["Date of Incident"])
            return
        save_case(
            name=data["Full Name"],
            contact=data["Contact"],
            case_type=data["Case Type"],
            date=parsed_date.strftime("%Y-%m-%d"),
            description=data["Description"]
        )
        print("Case saved successfully")
    except Exception as e:
        print("Error while saving case info:", e)