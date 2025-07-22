import streamlit as st
from core import extract_case_info_prompt_only, handle_case_storage
import base64
import json
import random


def strip_json_from_reply(reply):
    try:
        json_start = reply.find("{")
        json_end = reply.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            return reply[json_end:].strip()
    except:
        pass
    return reply.strip()


st.set_page_config(page_title="Jed.ai Legal Assistant")



st.title("Jed.ai Legal Assistant")
st.markdown("Ask a legal question below or describe an incident.")


if "chat_blocks" not in st.session_state:
    st.session_state.chat_blocks = []

if "case_data" not in st.session_state:
    st.session_state.case_data = {
        "Full Name": "",
        "Contact": "",
        "Case Type": "",
        "Date of Incident": "",
        "Description": ""
    }

if "field_queue" not in st.session_state:
    st.session_state.field_queue = []

if "awaiting_field" not in st.session_state:
    st.session_state.awaiting_field = None

def get_conversational_prompt(field):
    prompts = {
        "Full Name": [
            "I really appreciate you sharing that. Mind letting me know your name?",
            "Thanks for telling me that. What’s your full name so I can make a proper note?",
            "Got it — what's your name, just so I can make sure we keep things organized?"
        ],
        "Contact": [
            "Could I get a phone number or email to follow up if needed?",
            "How can we reach you later if we need to follow up?",
            "Appreciate that. May I get your contact number or email?"
        ],
        "Date of Incident": [
            "When did this happen, if you remember?",
            "Can you share when the incident occurred?",
            "Just so we get the timeline right — when was this?"
        ],
        "Description": [
            "Would you be open to sharing a quick summary of what happened?",
            "Can you briefly describe what happened?",
            "If you're okay with it, a short description would help us understand better."
        ],
        "Case Type": [
            "What type of incident was it? (Car accident, slip and fall, etc.)",
            "Just to clarify, what kind of case is this?",
            "Can you tell me what type of situation this was?"
        ]
    }
    return random.choice(prompts.get(field, ["Could you tell me more?"]))


def handle_submit():
    user_input = st.session_state.user_input.strip()

 
    if not user_input:
        return

    user_input = user_input.lower()

    legal_keywords =  ["should", "can i", "do i have", "is it legal", "sue", "lawsuit", "claim", "liable", "why"]
    if any(kw in user_input for kw in legal_keywords):
        gpt_output = extract_case_info_prompt_only(user_input)
        st.session_state.chat_blocks.append({
            "user": user_input,
            "assistant": gpt_output
        })
        st.session_state.awaiting_field = None
        st.session_state.user_input = ""
        return

 
    casual_inputs = [
        "hi", "hello", "hey", "how are you", "good morning", "good evening",
        "what's up", "sup", "yo", "how’s it going", "how r u"
    ]
    if user_input in casual_inputs:
        gpt_output = extract_case_info_prompt_only(user_input)
        st.session_state.chat_blocks.append({
            "user": user_input,
            "assistant": gpt_output
        })
        st.session_state.awaiting_field = None
        st.session_state.user_input = ""
        return

 
    if st.session_state.awaiting_field:
        field = st.session_state.awaiting_field
        st.session_state.case_data[field] = user_input
        missing = [k for k, v in st.session_state.case_data.items() if not v]
        st.session_state.field_queue = missing
        st.session_state.awaiting_field = missing[0] if missing else None

        follow_up = ""
        if st.session_state.awaiting_field:
            follow_up = get_conversational_prompt(st.session_state.awaiting_field)

        st.session_state.chat_blocks.append({
            "user": user_input,
            "assistant": f"{field} recorded. Thank you!" + (f"\n\n{follow_up}" if follow_up else "")
    })


        if not missing:
            json_ready = json.dumps(st.session_state.case_data)
            handle_case_storage(json_ready)
            st.session_state.chat_blocks.append({
                "user": "",
                "assistant": "Thank you for sharing your details. A member of our team will be in touch with you shortly to assist further."
            })

        st.session_state.user_input = ""
        return


    if user_input:
        gpt_output = extract_case_info_prompt_only(user_input)
        st.session_state.chat_blocks.append({
            "user": user_input,
            "assistant": gpt_output
        })

        try:
            json_start = gpt_output.find("{")
            json_end = gpt_output.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                json_block = gpt_output[json_start:json_end]
                data = json.loads(json_block)

             
                for key in st.session_state.case_data:
                    if key in data and data[key].strip():
                        st.session_state.case_data[key] = data[key].strip()

                
                filled_fields = [key for key in data if key in st.session_state.case_data and data[key].strip()]
                no_fields_updated = len(filled_fields) == 0

               
                if not no_fields_updated:
                    missing_fields = [key for key, val in st.session_state.case_data.items() if not val]
                    st.session_state.field_queue = missing_fields
                    st.session_state.awaiting_field = missing_fields[0] if missing_fields else None

                    if not missing_fields:
                        handle_case_storage(json_block)
                        st.session_state.chat_blocks.append({
                            "user": "",
                            "assistant": "Our human agent will reach out to you shortly."
                        })
                else:
                    st.session_state.awaiting_field = None

        except Exception as e:
            print("GPT response had no valid JSON:", e)


        st.session_state.user_input = ""


st.text_input("Ask a question:", key="user_input", on_change=handle_submit)
st.markdown("---")



for i, msg in reversed(list(enumerate(st.session_state.chat_blocks))):
    with st.container():
        st.markdown(f"**You said:** {msg['user']}")

        with st.expander("Jed.ai Legal Assistant's Response", expanded=True):
            assistant_reply = msg["assistant"].strip()

           
            if assistant_reply == "Case information received and stored.":
                st.markdown("*Case information received and stored.*")
            
            
            elif assistant_reply.endswith("recorded. Thank you!"):
                st.markdown(assistant_reply)

            
            elif st.session_state.awaiting_field:
                follow_up = get_conversational_prompt(st.session_state.awaiting_field)
                st.markdown(follow_up)

                
                if assistant_reply.startswith("{"):
                    json_end = assistant_reply.find("}") + 1
                    gpt_tail = assistant_reply[json_end:].strip()
                    if gpt_tail and not gpt_tail.startswith("{"):
                        st.markdown(gpt_tail.replace("\n", "  \n"))
                continue  

            
            else:
                clean_reply = strip_json_from_reply(assistant_reply)
                if clean_reply:
                    st.markdown(clean_reply.replace("\n", "  \n"))

        st.markdown("---")


