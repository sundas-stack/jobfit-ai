"""A small skills dictionary. Used by demo mode (no API key) to spot skills with simple rules."""

import re

# canonical name -> extra spellings
SKILLS: dict[str, list[str]] = {
    # languages
    "Python": [],
    "Java": [],
    "JavaScript": ["js", "es6"],
    "TypeScript": ["ts"],
    "Kotlin": [],
    "C++": ["cpp"],
    "C#": ["csharp", ".net"],
    "Go": ["golang"],
    "Rust": [],
    "SQL": [],
    "PHP": [],
    "Swift": [],
    "Dart": [],
    "HTML": ["html5"],
    "CSS": ["css3", "scss", "sass"],
    "Bash": ["shell"],
    # frontend / mobile
    "React": ["react.js", "reactjs"],
    "Next.js": ["nextjs"],
    "Angular": [],
    "Vue": ["vue.js"],
    "React Native": [],
    "Expo": [],
    "Flutter": [],
    "Android": [],
    "iOS": [],
    "Tailwind": ["tailwindcss"],
    "Redux": [],
    "Responsive design": ["responsive"],
    "Figma": [],
    "UI/UX": ["ux", "ui design", "user experience"],
    "Accessibility": ["a11y", "wcag"],
    "Jest": [],
    "Cypress": [],
    "Playwright": [],
    # backend / data
    "Node.js": ["node", "nodejs", "express"],
    "FastAPI": [],
    "Flask": [],
    "Django": [],
    "Spring Boot": ["spring"],
    "REST APIs": ["rest", "restful", "rest api", "api integration"],
    "GraphQL": [],
    "PostgreSQL": ["postgres"],
    "MySQL": [],
    "MongoDB": ["mongo"],
    "Redis": [],
    "Kafka": [],
    "Microservices": [],
    "Excel": ["ms excel", "microsoft excel", "spreadsheets"],
    "Google Sheets": ["google sheet"],
    "Data entry": ["data processing", "typing"],
    "Pandas": [],
    "NumPy": [],
    "Power BI": ["powerbi"],
    "Tableau": [],
    "Data analysis": ["data analytics"],
    # AI
    "Machine learning": ["ml"],
    "Deep learning": [],
    "TensorFlow": [],
    "PyTorch": [],
    "scikit-learn": ["sklearn"],
    "LLMs": ["llm", "large language models", "gpt", "generative ai", "genai"],
    "RAG": ["retrieval augmented"],
    "LangChain": [],
    "Prompt engineering": [],
    "NLP": ["natural language processing"],
    "OCR": [],
    "Computer vision": ["opencv"],
    "Vector databases": ["pgvector", "faiss", "pinecone", "vector db"],
    "AI agents": ["agents", "agentic", "tool calling", "function calling"],
    "MCP": ["model context protocol"],
    # devops / cloud
    "Docker": ["containers", "containerized"],
    "Kubernetes": ["k8s"],
    "CI/CD": ["ci cd", "github actions", "jenkins"],
    "Git": ["github", "gitlab", "version control"],
    "AWS": ["amazon web services"],
    "Azure": [],
    "GCP": ["google cloud"],
    "Linux": ["ubuntu"],
    "Terraform": [],
    "Testing": ["unit tests", "pytest", "automated testing", "qa"],
    # soft / ways of working
    "Communication": ["communicator", "presenting", "presentations"],
    "Teamwork": ["collaboration", "collaborate"],
    "Leadership": ["lead", "president", "mentoring"],
    "Problem solving": ["problem-solving"],
    "Agile": ["scrum", "jira", "sprint"],
    "Remote work": ["remote"],
}

SOFT = {"Communication", "Teamwork", "Leadership", "Problem solving", "Agile", "Remote work"}


def _pattern(name: str, aliases: list[str]) -> re.Pattern:
    words = [name, *aliases]
    parts = [re.escape(w.lower()) for w in sorted(words, key=len, reverse=True)]
    return re.compile(r"(?<![a-z0-9.])(" + "|".join(parts) + r")(?![a-z0-9+#])")


PATTERNS = {name: _pattern(name, aliases) for name, aliases in SKILLS.items()}


def find_skills(text: str) -> list[str]:
    low = text.lower()
    return [name for name, pat in PATTERNS.items() if pat.search(low)]


def mentions(skill: str, text: str) -> bool:
    pat = PATTERNS.get(skill) or _pattern(skill, [])
    return bool(pat.search(text.lower()))
