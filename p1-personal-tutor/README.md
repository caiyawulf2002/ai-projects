# Personal Learning Tutor (P1)
> An AI-powered Socratic tutor that adapts to your learning style per topic, tracks quiz performance, and maintains conversation memory across sessions.

## What it does
P1 is a conversational learning assistant that teaches through questions rather than lectures. It builds personalized syllabi, runs Socratic teaching sessions, quizzes you on material, and automatically infers your preferred learning style by analyzing how you ask questions. When you struggle with a topic, it remembers—and adjusts its teaching approach accordingly.

## Why it exists
This is the first project in a 5-project AI portfolio system. P1 serves as the "natural language interface" for the entire system—when other agents (financial analyzers, optimizers, LSTM models) produce structured outputs, P1 translates them into explanations anchored to what you already know. It's both a standalone learning tool and the human-facing layer for a multi-agent financial AI system.

## System flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 1: App Startup                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
[streamlit run app.py]
     │
     ▼
[load_dotenv()]  ───► READ  .env file (OPENAI_API_KEY)
     │
     ▼
[st.set_page_config()]
     │
     ▼
[@st.cache_resource get_llm()]
     └─► Returns: ChatOpenAI(model="gpt-4o", temperature=0.7)
     │
     ▼
[@st.cache_resource get_profile_store()]
     └─► [ProfileStore.__init__()]
              └─► [_init_table()]  ───► WRITE  SQLite data/tutor.db
                       └─► CREATE TABLE IF NOT EXISTS user_profile
     │
     ▼
[@st.cache_resource get_score_tracker()]
     └─► [ScoreTracker.__init__()]  ───► WRITE  SQLite data/tutor.db
              └─► CREATE TABLE IF NOT EXISTS quiz_scores
     │
     ▼
? "memory" not in st.session_state
     └─► YES: [load_memory(llm)]  ───► READ  memory/session_memory.json
                   │
                   ▼
              ? file exists
                   ├─► YES: json.load() → reconstruct SessionMemory
                   │        from saved messages + summary
                   └─► NO:  Return fresh SessionMemory(llm, max_tokens=2000)
     │
     ▼
? "display_messages" not in st.session_state
     └─► YES: Iterate memory.messages
                   └─► Build list[tuple[str, str]] of (role, content)
     │
     ▼
? "page" not in st.session_state
     └─► [profile_store.load()]  ───► READ  SQLite user_profile
              │
              ▼
         ? profile exists
              ├─► YES: st.session_state.page = "chat"
              └─► NO:  st.session_state.page = "profile_setup"
     │
     ▼
[Render page based on st.session_state.page]


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 2: Profile Setup (First-time user)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
[_render_profile_setup()]
     │
     ▼
[st.form("profile_form")]
     │
     ├─► [st.selectbox("learning_style")]  → visual | auditory | reading | kinesthetic
     ├─► [st.selectbox("preferred_pace")]  → slow | medium | fast
     ├─► [st.selectbox("explanation_style")]  → analogies | step_by_step | examples_first | theory_first
     ├─► [st.text_input("weak_topics")]  → comma-separated string
     └─► [st.text_input("strong_topics")]  → comma-separated string
     │
     ▼
[st.form_submit_button("Save Profile")]
     │
     ▼
? form submitted
     │
     ▼
[UserProfile(...)]  ← Pydantic model instantiation
     │
     ▼
[profile_store.save(profile)]  ───► WRITE  SQLite user_profile
     │                                     (INSERT ... ON CONFLICT UPDATE)
     ▼
[st.session_state.page = "chat"]
     │
     ▼
[st.rerun()]


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 3: User sends a chat message                                          │
└─────────────────────────────────────────────────────────────────────────────┘
[User types in st.chat_input("Message P1...")]
     │
     ▼
[st.session_state.turn_count += 1]
     │
     ▼
[st.session_state.display_messages.append(("user", user_input))]
     │
     ▼
[st.session_state.memory.add_message("human", user_input)]
     │
     ▼
[_get_system_prompt()]
     │
     ├─► [profile_store.load()]  ───► READ  SQLite user_profile
     │        │
     │        ▼
     │   ? profile is None
     │        ├─► YES: Return TUTOR_SYSTEM_PROMPT with placeholder text
     │        └─► NO:  Continue to build_system_prompt
     │
     └─► [build_system_prompt(profile, topic)]
              │
              ├─► [_resolve_styles(profile, topic)]
              │        │
              │        ▼
              │   ? topic is not None
              │        └─► [profile.topic_styles.get(topic.lower().strip())]
              │                 │
              │                 ▼
              │            ? TopicStyle exists for topic
              │                 ├─► YES: Use topic overrides where non-None
              │                 └─► NO:  Use global defaults only
              │        │
              │        ▼
              │   Returns: (learning_style, pace, explanation_style, topic_style|None)
              │
              └─► [_render_profile_block(profile, topic)]
                       │
                       ▼
                  Build multi-line string with:
                       - Background: {profile.strong_topics}
                       - Gaps: {profile.weak_topics}
                       - Learning style: {resolved learning_style}
                       - Pace: {resolved pace with _PACE_LABELS}
                       - Explanation: {resolved explanation_style with _STYLE_LABELS}
                       - ? topic_style exists: add confidence level
                       │
                       ▼
                  Returns: str (profile block for system prompt)
              │
              ▼
         [TUTOR_SYSTEM_PROMPT.replace("{learner_profile}", profile_block)]
              │
              ▼
         Returns: str (complete system prompt)
     │
     ▼
[Build messages list for LLM]
     │
     ├─► [SystemMessage(system_prompt)]
     ├─► ? memory.running_summary not empty
     │        └─► [SystemMessage(f"Conversation so far: {summary}")]
     └─► [HumanMessage/AIMessage for each in memory.messages]
              └─► Convert {"role": "human"/"ai", "content": ...} to LangChain types
     │
     ▼
[llm.invoke(messages)]  ═══► OpenAI gpt-4o  (~1K–4K tokens)
     │
     ▼
Returns: AIMessage with content
     │
     ▼
[response_text = ai_message.content]
     │
     ▼
[st.session_state.memory.add_message("ai", response_text)]
     │
     ▼
[st.session_state.memory.maybe_summarize()]
     │
     ▼
? total tokens in messages > max_tokens (2000)
     ├─► NO:  Continue
     └─► YES: [_summarize_messages(oldest_messages)]
                   │
                   ▼
              Build summarization prompt with oldest messages
                   │
                   ▼
              [llm.invoke([HumanMessage("Summarize...")])]  ═══► OpenAI gpt-4o
                   │
                   ▼
              [memory.running_summary += new_summary]
                   │
                   ▼
              Remove oldest messages from buffer
     │
     ▼
[st.session_state.display_messages.append(("assistant", response_text))]
     │
     ▼
[save_memory(st.session_state.memory)]  ───► WRITE  memory/session_memory.json
     │                                              (atomic write via temp file)
     ▼
[_maybe_run_inference()]
     │
     ▼
? _current_topic() is empty
     └─► YES: Return (no inference without topic)
     │
     ▼
? turn_count % _INFERENCE_EVERY_N_TURNS (3) != 0
     └─► YES: Return (not time for inference yet)
     │
     ▼
? len(memory.messages) < 4
     └─► YES: Return (not enough conversation data)
     │
     ▼
[infer_style(topic, recent_messages, llm)]
     │
     ▼
     ┌────────────────────────────────────────────────┐
     │  SUB-FLOW: Style Inference Chain               │
     └────────────────────────────────────────────────┘
     [build_style_inference_chain(llm)]
          │
          ├─► [PydanticOutputParser(pydantic_object=StyleSignal)]
          │        └─► Generates format_instructions for JSON schema
          │
          └─► [ChatPromptTemplate.from_template(_INFERENCE_TEMPLATE)]
                   │
                   ▼
              Chain: prompt | llm | parser
          │
          ▼
     [format_conversation(messages[-6:])]  ← last 6 messages only
          │
          ▼
     Returns: str ("Learner: ...\nTutor: ...\n...")
          │
          ▼
     [chain.invoke({"topic": topic, "conversation": convo, 
                    "format_instructions": ...})]
          │
          ▼
     [ChatPromptTemplate.format()]
          │
          ▼
     [llm.invoke(formatted_prompt)]  ═══► OpenAI gpt-4o  (~500–1K tokens)
          │
          ▼
     Returns: AIMessage with JSON content
          │
          ▼
     [PydanticOutputParser.parse(content)]
          │
          ▼
     ? JSON valid and matches StyleSignal schema
          ├─► YES: Returns: StyleSignal(pace, explanation_style, 
          │                             learning_style, reasoning)
          └─► NO:  Raises OutputParserException
                        │
                        ▼
                   Caught by caller → inference silently discarded
     │
     ▼
[_apply_inference(signal, topic)]
     │
     ▼
[profile_store.load()]  ───► READ  SQLite user_profile
     │
     ▼
[profile_store.update_topic_style(topic, signal)]
     │
     ├─► [_normalise_topic(topic)]  → lowercase, stripped
     │
     ├─► ? topic_style already exists for this topic
     │        ├─► YES: [_merge_signal(existing_style, signal)]
     │        │             │
     │        │             ▼
     │        │        For each dimension (pace, explanation_style, learning_style):
     │        │             ? signal has non-None value
     │        │                  └─► Update TopicStyle field
     │        │             │
     │        │             ▼
     │        │        [observation_count += 1]
     │        │             │
     │        │             ▼
     │        │        [confidence = min(1.0, count / _CONFIDENCE_SATURATION)]
     │        │             └─► Saturation = 5 observations for 100% confidence
     │        │
     │        └─► NO:  Create new TopicStyle from signal with confidence = 0.2
     │
     └─► [profile_store.save(updated_profile)]  ───► WRITE  SQLite user_profile
     │
     ▼
[st.session_state.last_inference = signal.reasoning]
     │
     ▼
[st.rerun()]  ← Refresh UI to show updated inference status


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 4: User clicks "Start Quiz" button                                    │
└─────────────────────────────────────────────────────────────────────────────┘
[st.sidebar button "Start Quiz"]
     │
     ▼
? _current_topic() is empty
     └─► YES: [st.warning("Set a topic first")]
              └─► Return
     │
     ▼
[st.session_state.quiz_saved = False]
     │
     ▼
[Build quiz prompt]
     │
     ▼
[_get_system_prompt()]  ← same as Flow 3
     │
     ▼
[memory.add_message("human", f"Quiz me on {topic}. Ask 3-5 questions...")]
     │
     ▼
[llm.invoke(messages)]  ═══► OpenAI gpt-4o
     │
     ▼
[Display quiz questions in chat]
     │
     ▼
[save_memory(memory)]  ───► WRITE  memory/session_memory.json


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 5: User clicks "Score Quiz" button                                    │
└─────────────────────────────────────────────────────────────────────────────┘
[st.sidebar button "Score Quiz"]
     │
     ▼
? quiz_saved is True
     └─► YES: [st.info("Quiz already scored")]
              └─► Return
     │
     ▼
[score_quiz(topic, memory.messages, llm)]
     │
     ▼
     ┌────────────────────────────────────────────────┐
     │  SUB-FLOW: Quiz Scoring Chain                  │
     └────────────────────────────────────────────────┘
     [build_quiz_scoring_chain(llm)]
          │
          ├─► [PydanticOutputParser(pydantic_object=QuizResult)]
          │
          ├─► [OutputFixingParser.from_llm(parser, llm)]
          │        └─► Wraps primary parser with auto-repair on failure
          │
          └─► [ChatPromptTemplate.from_template(_SCORING_TEMPLATE)]
          │
          ▼
     Chain: prompt | llm | fixing_parser
          │
          ▼
     [format_conversation(messages)]
          │
          ▼
     Returns: str ("Learner: ...\nTutor: ...\n...")
          │
          ▼
     [chain.invoke({"topic": topic, "conversation": convo, 
                    "today": date.today(), "format_instructions": ...})]
          │
          ▼
     [llm.invoke(formatted_prompt)]  ═══► OpenAI gpt-4o  (~1K–2K tokens)
          │
          ▼
     Returns: AIMessage with JSON content
          │
          ▼
     [OutputFixingParser.parse(content)]
          │
          ▼
     ? JSON valid
          ├─