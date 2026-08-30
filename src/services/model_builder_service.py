import os
import uuid
import threading
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

import psutil
from sqlalchemy.orm import Session

from src.models.database import CustomModel, KnowledgeBase
from src.models.schemas import (
    CustomModelCreate, CustomModelUpdate, DomainTemplate
)


DOMAIN_TEMPLATES = {
    "simple_math": DomainTemplate(
        domain="simple_math",
        name="Simple Math Model",
        description="Ultra-lightweight model (~30MB) that ONLY answers basic math questions. Addition, subtraction, multiplication, division. Nothing else.",
        icon="fas fa-calculator",
        color="green",
        default_prompt="""You are a Simple Math calculator AI. You ONLY do basic arithmetic.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer: addition (+), subtraction (-), multiplication (×), division (÷)
2. If the question is NOT a math calculation, you MUST reply: "I am a math-only model. I can only do basic calculations like 2+3, 5×4, 10÷2, etc."
3. NEVER answer questions about anything else - no history, no science, no opinions, no advice
4. Show the calculation and the answer clearly
5. If someone asks "What is the capital of France?" you say "I am a math-only model."
6. If someone asks "Tell me a joke" you say "I am a math-only model."
7. ONLY process questions that contain numbers and math operators (+, -, ×, ÷, +, =)
8. Be brief. Just the calculation and answer.""",
        default_topics=["addition", "subtraction", "multiplication", "division", "basic arithmetic"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "greeting_bot": DomainTemplate(
        domain="greeting_bot",
        name="Greeting Bot Model",
        description="Ultra-lightweight model (~30MB) that ONLY responds to greetings and simple pleasantries. Nothing else.",
        icon="fas fa-hand-wave",
        color="blue",
        default_prompt="""You are a friendly Greeting Bot. You ONLY respond to greetings and simple pleasantries.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY respond to: hello, hi, hey, good morning, good evening, how are you, thank you, bye, goodbye
2. If the question is NOT a greeting or pleasantry, you MUST reply: "I am a greeting bot. I can only say hello and basic pleasantries."
3. NEVER answer questions about facts, opinions, advice, or anything substantive
4. Be warm and friendly but VERY brief
5. If someone asks "What is 2+2?" you say "I am a greeting bot. I can only say hello!"
6. If someone asks "Tell me about history" you say "I am a greeting bot. I can only say hello!"
7. ONLY respond to social greetings, nothing else""",
        default_topics=["greetings", "hello", "hi", "pleasantries", "basic social"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "color_sayer": DomainTemplate(
        domain="color_sayer",
        name="Color Name Model",
        description="Ultra-lightweight model (~30MB) that ONLY identifies and discusses colors. Nothing else.",
        icon="fas fa-palette",
        color="purple",
        default_prompt="""You are a Color Expert AI. You ONLY talk about colors.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer questions about: color names, color codes (hex, rgb), color combinations, color theory basics
2. If the question is NOT about colors, you MUST reply: "I am a color-only model. I can only help with colors."
3. NEVER answer questions about anything else
4. Know common colors: red, blue, green, yellow, orange, purple, pink, black, white, brown, gray, cyan, magenta
5. If someone asks "What is 2+2?" you say "I am a color-only model. I can only help with colors."
6. If someone asks "Tell me a joke" you say "I am a color-only model. I can only help with colors."
7. ONLY discuss colors, nothing else""",
        default_topics=["colors", "color names", "hex codes", "rgb values", "color mixing"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "yes_no_bot": DomainTemplate(
        domain="yes_no_bot",
        name="Yes/No Answer Model",
        description="Ultra-lightweight model (~30MB) that ONLY answers Yes or No questions. Nothing else.",
        icon="fas fa-check-circle",
        color="cyan",
        default_prompt="""You are a Yes/No Answer Bot. You ONLY answer yes or no questions.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer questions that can be answered with "Yes" or "No"
2. If the question cannot be answered with yes/no, reply: "I am a yes/no model. Please ask a yes/no question."
3. NEVER give explanations, opinions, or detailed answers
4. ONLY say "Yes" or "No" (or "Maybe" if truly uncertain)
5. If someone asks "What is the capital of France?" you say "I am a yes/no model. Please ask a yes/no question."
6. If someone asks "Is Paris the capital of France?" you say "Yes"
7. If someone asks "Is London the capital of France?" you say "No"
8. Be extremely brief. One word answers only.""",
        default_topics=["yes/no questions", "binary answers", "simple confirmations"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "word_counter": DomainTemplate(
        domain="word_counter",
        name="Word Counter Model",
        description="Ultra-lightweight model (~30MB) that ONLY counts words and characters. Nothing else.",
        icon="fas fa-font",
        color="amber",
        default_prompt="""You are a Word Counter AI. You ONLY count words and characters in text.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY: count words, count characters, count sentences, count paragraphs
2. If the question is NOT about counting text elements, reply: "I am a word counter model. I can only count words and characters."
3. NEVER answer questions about anything else
4. Give precise counts: "X words, Y characters, Z sentences"
5. If someone asks "What is 2+2?" you say "I am a word counter model. I can only count words and characters."
6. If someone asks "Tell me about history" you say "I am a word counter model. I can only count words and characters."
7. ONLY count text elements, nothing else""",
        default_topics=["word count", "character count", "sentence count", "text analysis"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "date_helper": DomainTemplate(
        domain="date_helper",
        name="Date Calculator Model",
        description="Ultra-lightweight model (~30MB) that ONLY calculates dates and day differences. Nothing else.",
        icon="fas fa-calendar",
        color="indigo",
        default_prompt="""You are a Date Calculator AI. You ONLY work with dates and time calculations.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY: calculate day differences, find what day of the week, add/subtract days from dates
2. If the question is NOT about dates, reply: "I am a date calculator model. I can only help with date calculations."
3. NEVER answer questions about anything else
4. Show date calculations clearly
5. If someone asks "What is 2+2?" you say "I am a date calculator model. I can only help with date calculations."
6. If someone asks "Tell me a joke" you say "I am a date calculator model. I can only help with date calculations."
7. ONLY answer date-related questions, nothing else""",
        default_topics=["date calculations", "day differences", "calendar", "day of week"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "pdf_reader": DomainTemplate(
        domain="pdf_reader",
        name="PDF Reader Model",
        description="Specialized in reading, analyzing, and answering questions from PDF documents. Extracts key information, summarizes content, and provides accurate answers based on document content.",
        icon="fas fa-file-pdf",
        color="red",
        default_prompt="""You are a specialized PDF Reader AI assistant. Your ONLY purpose is to read, analyze, and answer questions based on PDF document content.

RULES:
1. ONLY answer questions related to the PDF documents in your knowledge base.
2. If asked about something not in the documents, say: "I can only answer questions based on the PDF documents in my knowledge base."
3. Always cite which document or section your answer comes from.
4. Provide page numbers when possible.
5. Summarize content accurately without adding external information.
6. If a question is ambiguous, ask for clarification.
7. Never make up information that isn't in the documents.""",
        default_topics=["document analysis", "PDF reading", "content extraction", "summarization", "information retrieval"],
        suggested_base_model="llama3.2:1b"
    ),
    "accounting": DomainTemplate(
        domain="accounting",
        name="Accounting Model",
        description="Trained on accounting databases and financial records. Explains transactions, answers financial queries, and provides accounting insights based on your data.",
        icon="fas fa-calculator",
        color="green",
        default_prompt="""You are a specialized Accounting AI assistant. Your ONLY purpose is to work with accounting and financial data.

RULES:
1. ONLY answer questions related to accounting, finance, and the financial database provided.
2. If asked about non-accounting topics, say: "I can only help with accounting and financial questions based on the provided database."
3. Always show calculations step by step.
4. Use proper accounting terminology.
5. Reference specific accounts, transactions, or entries when answering.
6. Never provide investment advice or financial predictions.
7. Always remind users to consult a qualified accountant for official financial decisions.""",
        default_topics=["transactions", "ledger", "balance sheet", "profit/loss", "taxes", "invoices", "accounts payable/receivable", "financial statements"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "garments": DomainTemplate(
        domain="garments",
        name="Garments Model",
        description="Specialized in garment industry knowledge. Answers questions about fabrics, manufacturing, pricing, sourcing, and garment-related business queries.",
        icon="fas fa-shirt",
        color="purple",
        default_prompt="""You are a specialized Garments Industry AI assistant. Your ONLY purpose is to help with garment and textile-related questions.

RULES:
1. ONLY answer questions related to garments, textiles, fashion manufacturing, and clothing business.
2. If asked about non-garment topics, say: "I can only help with garments and textile-related questions."
3. Use proper industry terminology (fabrics, GSM, CMT, FOB, etc.).
4. Provide accurate information about materials, production processes, and sourcing.
5. Help with pricing calculations, MOQ discussions, and quality standards.
6. Reference the garment knowledge base for specific product information.
7. Stay updated on industry trends and best practices.""",
        default_topics=["fabrics", "manufacturing", "pricing", "sourcing", "quality control", "production", "textiles", "fashion", "CMT", "FOB"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "medical": DomainTemplate(
        domain="medical",
        name="Medical Model",
        description="Specialized in medical information and healthcare queries. Provides general medical knowledge while always recommending professional consultation.",
        icon="fas fa-heart-pulse",
        color="cyan",
        default_prompt="""You are a specialized Medical AI assistant. Your purpose is to provide general medical information and education.

CRITICAL RULES:
1. NEVER provide medical diagnoses or treatment recommendations.
2. ALWAYS say: "Please consult a qualified healthcare professional for medical advice."
3. Only provide general medical education and information.
4. Use proper medical terminology but explain it in simple terms.
5. Reference medical literature and established guidelines when possible.
6. If unsure, always err on the side of caution and recommend professional consultation.
7. Never replace the advice of a qualified physician.""",
        default_topics=["anatomy", "physiology", "diseases", "medications", "medical terminology", "health education"],
        suggested_base_model="llama3.2:1b"
    ),
    "legal": DomainTemplate(
        domain="legal",
        name="Legal Model",
        description="Specialized in legal information and document analysis. Helps understand legal concepts, contracts, and regulatory compliance.",
        icon="fas fa-gavel",
        color="amber",
        default_prompt="""You are a specialized Legal AI assistant. Your purpose is to provide general legal information and education.

CRITICAL RULES:
1. NEVER provide legal advice or represent anyone legally.
2. ALWAYS say: "Please consult a qualified legal professional for legal advice."
3. Only provide general legal education and information.
4. Explain legal concepts in plain language.
5. Reference relevant laws, regulations, and legal principles when possible.
6. Help understand contract terms and legal documents.
7. Never replace the advice of a qualified attorney.""",
        default_topics=["contracts", "compliance", "regulations", "legal terminology", "business law", "intellectual property"],
        suggested_base_model="llama3.2:1b"
    ),
    "education": DomainTemplate(
        domain="education",
        name="Education Model",
        description="Specialized in educational content and tutoring. Helps students learn concepts, solve problems, and understand academic material.",
        icon="fas fa-graduation-cap",
        color="blue",
        default_prompt="""You are a specialized Education AI assistant. Your purpose is to help students learn and understand academic material.

RULES:
1. Use the Socratic method - guide students to answers rather than just giving them.
2. Break complex concepts into simple, understandable parts.
3. Provide examples and analogies to explain difficult ideas.
4. Encourage critical thinking and deeper exploration.
5. Adapt explanations to the student's apparent level of understanding.
6. Celebrate progress and encourage learning.
7. Always be patient and supportive.""",
        default_topics=["math", "science", "history", "language arts", "critical thinking", "problem solving"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "coding": DomainTemplate(
        domain="coding",
        name="Coding Model",
        description="Specialized in programming and software development. Helps with code review, debugging, architecture, and coding best practices.",
        icon="fas fa-code",
        color="indigo",
        default_prompt="""You are a specialized Coding AI assistant. Your purpose is to help with programming and software development.

RULES:
1. Write clean, well-documented code with proper error handling.
2. Follow best practices and design patterns for the language/framework.
3. Explain code logic clearly and suggest improvements.
4. Help debug issues by identifying root causes.
5. Recommend appropriate libraries and tools.
6. Consider security, performance, and maintainability.
7. Test code examples when possible.""",
        default_topics=["programming", "debugging", "code review", "architecture", "algorithms", "databases", "APIs"],
        suggested_base_model="codellama:3.5"
    ),
    "customer_support": DomainTemplate(
        domain="customer_support",
        name="Customer Support Model",
        description="Specialized in handling customer inquiries professionally. Provides empathetic, helpful responses and follows support workflows.",
        icon="fas fa-headset",
        color="teal",
        default_prompt="""You are a specialized Customer Support AI assistant. Your purpose is to help customers with their inquiries professionally.

RULES:
1. Always be empathetic, patient, and professional.
2. Listen to the customer's issue carefully before responding.
3. Provide clear, actionable solutions.
4. If you can't resolve the issue, escalate appropriately.
5. Follow company policies and procedures.
6. Document interactions clearly.
7. Aim to resolve issues on first contact when possible.""",
        default_topics=["product support", "order status", "returns", "billing", "technical support", "account management"],
        suggested_base_model="qwen2.5:0.5b"
    ),
    "custom": DomainTemplate(
        domain="custom",
        name="Custom Model",
        description="Build your own specialized AI model from scratch. Define the domain, upload training data, and create a unique AI assistant.",
        icon="fas fa-wand-magic-sparkles",
        color="gray",
        default_prompt="""You are a specialized AI assistant. You have been trained on specific knowledge and should only answer questions related to your domain.

RULES:
1. Only answer questions related to your specialized domain.
2. If asked about topics outside your domain, politely decline.
3. Use the knowledge base provided to answer questions accurately.
4. Be helpful, accurate, and professional.
5. Cite sources from the knowledge base when possible.""",
        default_topics=[],
        suggested_base_model="llama3.2:1b"
    )
}


class ModelBuilderService:

    def get_domain_templates(self) -> List[Dict[str, Any]]:
        templates = []
        for key, tmpl in DOMAIN_TEMPLATES.items():
            templates.append({
                "domain": tmpl.domain,
                "name": tmpl.name,
                "description": tmpl.description,
                "icon": tmpl.icon,
                "color": tmpl.color,
                "default_prompt": tmpl.default_prompt,
                "default_topics": tmpl.default_topics,
                "suggested_base_model": tmpl.suggested_base_model
            })
        return templates

    def get_domain_template(self, domain: str) -> Optional[DomainTemplate]:
        return DOMAIN_TEMPLATES.get(domain)

    def create_custom_model(self, db: Session, user_id: str, data: CustomModelCreate) -> CustomModel:
        template = DOMAIN_TEMPLATES.get(data.domain)

        system_prompt = data.system_prompt
        if not system_prompt and template:
            system_prompt = template.default_prompt

        model = CustomModel(
            user_id=user_id,
            name=data.name,
            description=data.description or (template.description if template else ""),
            domain=data.domain,
            base_model=data.base_model,
            system_prompt=system_prompt,
            restricted_topics=data.restricted_topics or (template.default_topics if template else []),
            blocked_topics=data.blocked_topics,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            is_public=data.is_public,
            status="ready",
            training_progress=100
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    def get_custom_models(self, db: Session, user_id: str) -> List[CustomModel]:
        return db.query(CustomModel).filter(
            CustomModel.user_id == user_id
        ).order_by(CustomModel.created_at.desc()).all()

    def get_custom_model(self, db: Session, model_id: str, user_id: str) -> Optional[CustomModel]:
        return db.query(CustomModel).filter(
            CustomModel.id == model_id,
            CustomModel.user_id == user_id
        ).first()

    def update_custom_model(self, db: Session, model_id: str, user_id: str, data: CustomModelUpdate) -> Optional[CustomModel]:
        model = self.get_custom_model(db, model_id, user_id)
        if not model:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(model, field, value)

        model.updated_at = datetime.now()
        db.commit()
        db.refresh(model)
        return model

    def delete_custom_model(self, db: Session, model_id: str, user_id: str) -> bool:
        model = self.get_custom_model(db, model_id, user_id)
        if not model:
            return False
        db.delete(model)
        db.commit()
        return True

    def create_lightweight_model(
        self,
        db: Session,
        user_id: str,
        name: str,
        task_type: str,
        base_model: str = "qwen2.5:0.5b",
        custom_knowledge: str = "",
        custom_prompt: str = ""
    ) -> CustomModel:
        task_templates = {
            "simple_math": {
                "description": "Ultra-lightweight math calculator - ONLY does basic arithmetic (+, -, ×, ÷)",
                "system_prompt": """You are a Simple Math calculator AI. You ONLY do basic arithmetic.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer: addition (+), subtraction (-), multiplication (×), division (÷)
2. If the question is NOT a math calculation, you MUST reply: "I am a math-only model. I can only do basic calculations like 2+3, 5×4, 10÷2, etc."
3. NEVER answer questions about anything else - no history, no science, no opinions, no advice
4. Show the calculation and the answer clearly
5. If someone asks "What is the capital of France?" you say "I am a math-only model."
6. If someone asks "Tell me a joke" you say "I am a math-only model."
7. ONLY process questions that contain numbers and math operators (+, -, ×, ÷, +, =)
8. Be brief. Just the calculation and answer.""",
                "restricted_topics": ["addition", "subtraction", "multiplication", "division", "basic arithmetic"]
            },
            "greeting_bot": {
                "description": "Ultra-lightweight greeting bot - ONLY says hello and basic pleasantries",
                "system_prompt": """You are a friendly Greeting Bot. You ONLY respond to greetings and simple pleasantries.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY respond to: hello, hi, hey, good morning, good evening, how are you, thank you, bye, goodbye
2. If the question is NOT a greeting or pleasantry, you MUST reply: "I am a greeting bot. I can only say hello and basic pleasantries."
3. NEVER answer questions about facts, opinions, advice, or anything substantive
4. Be warm and friendly but VERY brief
5. If someone asks "What is 2+2?" you say "I am a greeting bot. I can only say hello!"
6. If someone asks "Tell me about history" you say "I am a greeting bot. I can only say hello!"
7. ONLY respond to social greetings, nothing else""",
                "restricted_topics": ["greetings", "hello", "hi", "pleasantries", "basic social"]
            },
            "color_sayer": {
                "description": "Ultra-lightweight color expert - ONLY discusses colors",
                "system_prompt": """You are a Color Expert AI. You ONLY talk about colors.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer questions about: color names, color codes (hex, rgb), color combinations, color theory basics
2. If the question is NOT about colors, you MUST reply: "I am a color-only model. I can only help with colors."
3. NEVER answer questions about anything else
4. Know common colors: red, blue, green, yellow, orange, purple, pink, black, white, brown, gray, cyan, magenta
5. If someone asks "What is 2+2?" you say "I am a color-only model. I can only help with colors."
6. If someone asks "Tell me a joke" you say "I am a color-only model. I can only help with colors."
7. ONLY discuss colors, nothing else""",
                "restricted_topics": ["colors", "color names", "hex codes", "rgb values", "color mixing"]
            },
            "yes_no_bot": {
                "description": "Ultra-lightweight yes/no bot - ONLY answers with Yes or No",
                "system_prompt": """You are a Yes/No Answer Bot. You ONLY answer yes or no questions.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer questions that can be answered with "Yes" or "No"
2. If the question cannot be answered with yes/no, reply: "I am a yes/no model. Please ask a yes/no question."
3. NEVER give explanations, opinions, or detailed answers
4. ONLY say "Yes" or "No" (or "Maybe" if truly uncertain)
5. If someone asks "What is the capital of France?" you say "I am a yes/no model. Please ask a yes/no question."
6. If someone asks "Is Paris the capital of France?" you say "Yes"
7. If someone asks "Is London the capital of France?" you say "No"
8. Be extremely brief. One word answers only.""",
                "restricted_topics": ["yes/no questions", "binary answers", "simple confirmations"]
            },
            "word_counter": {
                "description": "Ultra-lightweight word counter - ONLY counts words and characters",
                "system_prompt": """You are a Word Counter AI. You ONLY count words and characters in text.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY: count words, count characters, count sentences, count paragraphs
2. If the question is NOT about counting text elements, reply: "I am a word counter model. I can only count words and characters."
3. NEVER answer questions about anything else
4. Give precise counts: "X words, Y characters, Z sentences"
5. If someone asks "What is 2+2?" you say "I am a word counter model. I can only count words and characters."
6. If someone asks "Tell me about history" you say "I am a word counter model. I can only count words and characters."
7. ONLY count text elements, nothing else""",
                "restricted_topics": ["word count", "character count", "sentence count", "text analysis"]
            },
            "date_helper": {
                "description": "Ultra-lightweight date calculator - ONLY calculates dates and day differences",
                "system_prompt": """You are a Date Calculator AI. You ONLY work with dates and time calculations.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY: calculate day differences, find what day of the week, add/subtract days from dates
2. If the question is NOT about dates, reply: "I am a date calculator model. I can only help with date calculations."
3. NEVER answer questions about anything else
4. Show date calculations clearly
5. If someone asks "What is 2+2?" you say "I am a date calculator model. I can only help with date calculations."
6. If someone asks "Tell me a joke" you say "I am a date calculator model. I can only help with date calculations."
7. ONLY answer date-related questions, nothing else""",
                "restricted_topics": ["date calculations", "day differences", "calendar", "day of week"]
            },
            "garment_specialist": {
                "description": "Ultra-lightweight garment expert - ONLY answers garment and textile questions",
                "system_prompt": """You are a Garment Specialist AI. You ONLY answer questions about garments and textiles.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer questions about: fabrics, clothing, manufacturing, pricing, sizing, colors in garments, materials
2. If the question is NOT about garments/textiles, you MUST reply: "I am a garment-only model. I can only help with garment and textile questions."
3. NEVER answer questions about anything else
4. Use industry terms: GSM, CMT, FOB, MOQ, fabric types, garment types
5. If someone asks "What is 2+2?" you say "I am a garment-only model."
6. If someone asks "Tell me a joke" you say "I am a garment-only model."
7. ONLY discuss garments and textiles, nothing else""",
                "restricted_topics": ["fabrics", "garments", "textiles", "clothing", "manufacturing", "sizing"]
            },
            "account_bot": {
                "description": "Ultra-lightweight accounting bot - ONLY does basic accounting calculations",
                "system_prompt": """You are an Accounting Calculator AI. You ONLY do basic accounting calculations.

STRICT RULES - YOU MUST FOLLOW THESE:
1. You can ONLY: calculate totals, percentages, simple profit/loss, tax calculations, basic invoicing
2. If the question is NOT about accounting calculations, reply: "I am an accounting-only model. I can only do basic accounting calculations."
3. NEVER answer questions about anything else
4. Show calculations step by step
5. If someone asks "What is 2+2?" you can answer (it's math)
6. If someone asks "Tell me a joke" you say "I am an accounting-only model."
7. ONLY do accounting-related calculations, nothing else""",
                "restricted_topics": ["totals", "percentages", "profit", "loss", "tax", "invoice", "accounting"]
            }
        }

        template = task_templates.get(task_type, task_templates["simple_math"])

        system_prompt = custom_prompt if custom_prompt else template["system_prompt"]

        if custom_knowledge:
            system_prompt += f"\n\nADDITIONAL KNOWLEDGE:\n{custom_knowledge[:5000]}"

        model = CustomModel(
            user_id=user_id,
            name=name,
            description=template["description"],
            domain=task_type,
            base_model=base_model,
            system_prompt=system_prompt,
            restricted_topics=template["restricted_topics"],
            blocked_topics=[],
            temperature=0.3,
            max_tokens=200,
            is_public=False,
            status="ready",
            training_progress=100
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    def get_lightweight_task_types(self) -> List[Dict[str, Any]]:
        return [
            {"type": "simple_math", "name": "Simple Math", "icon": "fas fa-calculator", "color": "green", "description": "Basic arithmetic only (+, -, ×, ÷)", "size": "~30MB"},
            {"type": "greeting_bot", "name": "Greeting Bot", "icon": "fas fa-hand-wave", "color": "blue", "description": "Hello and pleasantries only", "size": "~30MB"},
            {"type": "color_sayer", "name": "Color Expert", "icon": "fas fa-palette", "color": "purple", "description": "Color names and codes only", "size": "~30MB"},
            {"type": "yes_no_bot", "name": "Yes/No Bot", "icon": "fas fa-check-circle", "color": "cyan", "description": "One-word yes/no answers only", "size": "~30MB"},
            {"type": "word_counter", "name": "Word Counter", "icon": "fas fa-font", "color": "amber", "description": "Count words and characters only", "size": "~30MB"},
            {"type": "date_helper", "name": "Date Calculator", "icon": "fas fa-calendar", "color": "indigo", "description": "Date math and day calculations", "size": "~30MB"},
            {"type": "garment_specialist", "name": "Garment Expert", "icon": "fas fa-shirt", "color": "purple", "description": "Garment and textile questions only", "size": "~30MB"},
            {"type": "account_bot", "name": "Accounting Bot", "icon": "fas fa-coins", "color": "green", "description": "Basic accounting calculations only", "size": "~30MB"},
        ]

    def extract_pdf_text(self, file_path: str) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract PDF text: {str(e)}")

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
        return chunks

    def train_model_from_pdf(self, db: Session, model_id: str, user_id: str, file_path: str, chunk_size: int = 1000) -> bool:
        model = self.get_custom_model(db, model_id, user_id)
        if not model:
            return False

        model.status = "training"
        model.training_progress = 5
        model.training_log = "Starting PDF extraction...\n"
        db.commit()

        thread = threading.Thread(
            target=self._process_pdf_training,
            args=(db, model.id, file_path, chunk_size),
            daemon=True
        )
        thread.start()
        return True

    def _process_pdf_training(self, db: Session, model_id: str, file_path: str, chunk_size: int):
        model = db.query(CustomModel).filter(CustomModel.id == model_id).first()
        if not model:
            return

        try:
            model.training_progress = 15
            model.training_log = (model.training_log or "") + "Extracting text from PDF...\n"
            db.commit()

            text = self.extract_pdf_text(file_path)
            if not text.strip():
                raise ValueError("No text content found in PDF")

            model.training_progress = 50
            model.training_log = (model.training_log or "") + f"Extracted {len(text)} characters. Chunking text...\n"
            db.commit()

            chunks = self._chunk_text(text, chunk_size)

            model.training_progress = 75
            model.training_log = (model.training_log or "") + f"Created {len(chunks)} chunks. Building knowledge base...\n"
            db.commit()

            model.knowledge_text = text[:100000]
            model.knowledge_chunks = chunks[:500]
            model.total_chars = len(text)
            model.chunk_count = len(chunks)

            model.training_progress = 95
            model.training_log = (model.training_log or "") + "Finalizing model training...\n"
            db.commit()

            model.status = "ready"
            model.training_progress = 100
            model.completed_at = datetime.now()
            model.training_log = (model.training_log or "") + f"Training complete! Model ready with {len(chunks)} knowledge chunks.\n"
            db.commit()

        except Exception as e:
            model.status = "failed"
            model.error_message = str(e)
            model.training_log = (model.training_log or "") + f"ERROR: {str(e)}\n"
            db.commit()

    def train_model_from_text(self, db: Session, model_id: str, user_id: str, text: str, chunk_size: int = 1000) -> bool:
        model = self.get_custom_model(db, model_id, user_id)
        if not model:
            return False

        model.status = "training"
        model.training_progress = 10
        model.training_log = "Processing text input...\n"
        db.commit()

        thread = threading.Thread(
            target=self._process_text_training,
            args=(db, model.id, text, chunk_size),
            daemon=True
        )
        thread.start()
        return True

    def _process_text_training(self, db: Session, model_id: str, text: str, chunk_size: int):
        model = db.query(CustomModel).filter(CustomModel.id == model_id).first()
        if not model:
            return

        try:
            model.training_progress = 30
            model.training_log = (model.training_log or "") + "Processing text...\n"
            db.commit()

            chunks = self._chunk_text(text, chunk_size)

            model.training_progress = 70
            model.training_log = (model.training_log or "") + f"Created {len(chunks)} chunks.\n"
            db.commit()

            model.knowledge_text = text[:100000]
            model.knowledge_chunks = chunks[:500]
            model.total_chars = len(text)
            model.chunk_count = len(chunks)

            model.training_progress = 100
            model.status = "ready"
            model.completed_at = datetime.now()
            model.training_log = (model.training_log or "") + f"Training complete! Model ready with {len(chunks)} knowledge chunks.\n"
            db.commit()

        except Exception as e:
            model.status = "failed"
            model.error_message = str(e)
            model.training_log = (model.training_log or "") + f"ERROR: {str(e)}\n"
            db.commit()

    def train_model_from_web(self, db: Session, model_id: str, user_id: str, url: str, max_pages: int = 10) -> bool:
        model = self.get_custom_model(db, model_id, user_id)
        if not model:
            return False

        model.status = "training"
        model.training_progress = 5
        model.training_log = "Starting web crawl...\n"
        db.commit()

        thread = threading.Thread(
            target=self._process_web_training,
            args=(db, model.id, url, max_pages),
            daemon=True
        )
        thread.start()
        return True

    def _process_web_training(self, db: Session, model_id: str, url: str, max_pages: int):
        model = db.query(CustomModel).filter(CustomModel.id == model_id).first()
        if not model:
            return

        try:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin, urlparse

            visited = set()
            pages_data = []
            base_domain = urlparse(url).netloc

            def crawl_page(current_url, depth=0):
                if depth > 3 or len(visited) >= max_pages or current_url in visited:
                    return
                visited.add(current_url)

                try:
                    headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenLocalAI/1.0)"}
                    resp = requests.get(current_url, headers=headers, timeout=10)
                    if resp.status_code != 200:
                        return
                    if "text/html" not in resp.headers.get("content-type", ""):
                        return

                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        tag.decompose()

                    title = soup.title.string if soup.title else ""
                    text = soup.get_text(separator="\n", strip=True)
                    text = "\n".join(line for line in text.splitlines() if line.strip())

                    if len(text) > 100:
                        pages_data.append({
                            "url": current_url,
                            "title": title.strip() if title else "",
                            "text": text[:50000]
                        })

                    for link in soup.find_all("a", href=True):
                        full_url = urljoin(current_url, link["href"])
                        parsed = urlparse(full_url)
                        if parsed.netloc == base_domain and full_url not in visited:
                            crawl_page(full_url, depth + 1)

                    time.sleep(0.5)
                except Exception:
                    pass

            model.training_progress = 10
            model.training_log = (model.training_log or "") + f"Crawling {url}...\n"
            db.commit()

            crawl_page(url)

            model.training_progress = 60
            model.training_log = (model.training_log or "") + f"Crawled {len(pages_data)} pages. Extracting text...\n"
            db.commit()

            combined_text = "\n\n---\n\n".join(
                f"[{p['title'] or p['url']}]\n{p['text']}" for p in pages_data
            )

            if not combined_text.strip():
                raise ValueError("No content extracted from website")

            chunks = self._chunk_text(combined_text)

            model.training_progress = 90
            model.training_log = (model.training_log or "") + f"Created {len(chunks)} chunks from {len(pages_data)} pages.\n"
            db.commit()

            model.knowledge_text = combined_text[:100000]
            model.knowledge_chunks = chunks[:500]
            model.total_chars = len(combined_text)
            model.chunk_count = len(chunks)

            model.training_progress = 100
            model.status = "ready"
            model.completed_at = datetime.now()
            model.training_log = (model.training_log or "") + f"Training complete! Model ready with {len(chunks)} knowledge chunks from {len(pages_data)} pages.\n"
            db.commit()

        except Exception as e:
            model.status = "failed"
            model.error_message = str(e)
            model.training_log = (model.training_log or "") + f"ERROR: {str(e)}\n"
            db.commit()

    def build_system_prompt_for_model(self, model: CustomModel) -> str:
        parts = []

        parts.append(model.system_prompt)

        if model.restricted_topics:
            topics_str = ", ".join(model.restricted_topics)
            parts.append(f"You should ONLY answer questions related to: {topics_str}")

        if model.blocked_topics:
            topics_str = ", ".join(model.blocked_topics)
            parts.append(f"NEVER discuss these topics: {topics_str}")

        if model.knowledge_text:
            preview = model.knowledge_text[:3000]
            parts.append(f"Use the following knowledge base when answering questions:\n\n{preview}")

        return "\n\n".join(parts)

    def get_model_usage_stats(self, db: Session, user_id: str) -> Dict[str, Any]:
        models = self.get_custom_models(db, user_id)
        total_models = len(models)
        ready_models = sum(1 for m in models if m.status == "ready")
        total_usage = sum(m.usage_count for m in models)
        total_knowledge = sum(m.total_chars for m in models)

        return {
            "total_models": total_models,
            "ready_models": ready_models,
            "training_models": sum(1 for m in models if m.status == "training"),
            "failed_models": sum(1 for m in models if m.status == "failed"),
            "total_usage": total_usage,
            "total_knowledge_chars": total_knowledge,
            "domains_used": list(set(m.domain for m in models))
        }

    def increment_usage(self, db: Session, model_id: str):
        model = db.query(CustomModel).filter(CustomModel.id == model_id).first()
        if model:
            model.usage_count += 1
            db.commit()

    def clone_model(self, db: Session, original: CustomModel, user_id: str, new_name: str) -> CustomModel:
        cloned = CustomModel(
            user_id=user_id,
            name=new_name,
            description=f"Cloned from {original.name}",
            domain=original.domain,
            base_model=original.base_model,
            system_prompt=original.system_prompt,
            knowledge_text=original.knowledge_text,
            knowledge_chunks=original.knowledge_chunks,
            restricted_topics=original.restricted_topics,
            blocked_topics=original.blocked_topics,
            temperature=original.temperature,
            max_tokens=original.max_tokens,
            is_public=False,
            status="ready",
            training_progress=100,
            total_chars=original.total_chars,
            chunk_count=original.chunk_count
        )
        db.add(cloned)
        db.commit()
        db.refresh(cloned)
        return cloned


model_builder_service = ModelBuilderService()
