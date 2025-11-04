#!/usr/bin/env python3
"""Seed initial knowledge base with sample meditation content"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ingestion.vectorstore import vector_store
from app.core.logging import get_logger

logger = get_logger(__name__)


SAMPLE_DOCUMENTS = [
    # Canonical Teachings
    {
        "content": """The Third Eye, or Ajna chakra, is the sixth primary chakra in the body according to Hindu tradition. 
        Located between the eyebrows, it is associated with intuition, wisdom, and spiritual insight. 
        The Ajna chakra is symbolized by a two-petaled lotus and is connected to the color indigo or deep blue.
        
        In yogic philosophy, the Third Eye represents the seat of consciousness and the gateway to higher awareness. 
        When balanced, it enhances clarity of thought, intuition, and the ability to see beyond physical reality.
        
        Traditional practices for awakening the Third Eye include meditation, pranayama (breath work), 
        and specific yoga asanas that stimulate this energy center.""",
        "title": "Third Eye Fundamentals",
        "source": "pdf",
        "page": 1,
        "section": "teachings"
    },
    
    # Safety Information
    {
        "content": """IMPORTANT SAFETY CONSIDERATIONS for Third Eye Meditation:
        
        1. Start Gradually: Begin with short sessions (5-10 minutes) and gradually increase duration.
        
        2. Contraindications:
           - Avoid intense Third Eye practices if you have a history of psychosis or severe mental illness
           - Those with epilepsy should consult a healthcare provider before beginning
           - Pregnant women should practice only gentle techniques
        
        3. Warning Signs to Stop:
           - Severe headaches or pressure in the forehead
           - Dizziness or disorientation lasting more than a few minutes
           - Anxiety or panic attacks
           - Insomnia or sleep disturbances
        
        4. When to Seek Professional Help:
           - If you experience persistent psychological distress
           - If meditation triggers traumatic memories
           - If you have concerns about your mental health
        
        Remember: Meditation is a complementary practice, not a substitute for medical or psychological treatment.""",
        "title": "Third Eye Safety Guidelines",
        "source": "pdf",
        "page": 15,
        "section": "safety"
    },
    
    # Practice Techniques
    {
        "content": """TRATAKA (Candle Gazing) - A Traditional Third Eye Practice
        
        Setup:
        - Sit comfortably in a darkened room
        - Place a candle at eye level, about 2-3 feet away
        - Ensure no drafts will disturb the flame
        
        Practice Steps:
        1. Sit with spine straight, shoulders relaxed
        2. Take 3-5 deep breaths to center yourself
        3. Gaze softly at the candle flame without blinking
        4. Continue for 1-3 minutes initially
        5. Close your eyes and visualize the flame at your Third Eye point
        6. Hold the inner image for as long as comfortable
        7. Repeat 2-3 times
        
        Duration: Start with 5-10 minutes total, gradually increase to 20 minutes
        
        Benefits:
        - Improves concentration and focus
        - Strengthens eye muscles
        - Calms the mind
        - Stimulates the Ajna chakra
        
        Precautions:
        - If eyes become strained, close them and rest
        - Never force yourself to keep eyes open if uncomfortable
        - Practice in a safe environment away from flammable materials""",
        "title": "Trataka Practice Guide",
        "source": "pdf",
        "page": 23,
        "section": "practices"
    },
    
    # Q&A Examples
    {
        "content": """Q: How long should I meditate on my Third Eye as a beginner?
        
        A: As a beginner, start with just 5-10 minutes per session. The Third Eye is a powerful energy center, 
        and overstimulation can lead to headaches or restlessness. Listen to your body and gradually increase 
        the duration as you become more comfortable. Quality is more important than quantity.
        
        Q: Is it normal to see colors or lights during Third Eye meditation?
        
        A: Yes, seeing colors (especially purple, indigo, or white light) is a common experience during 
        Third Eye meditation. These are often phosphenes (light sensations) or may indicate activation 
        of the Ajna chakra. Simply observe them without attachment. If the experiences become overwhelming, 
        reduce the intensity or duration of your practice.
        
        Q: Can Third Eye meditation help with anxiety?
        
        A: Third Eye meditation can help with anxiety by promoting mental clarity and inner peace. 
        However, it's important to note that for some people, intense concentration practices may 
        initially increase anxiety. If you have clinical anxiety, work with a qualified teacher and 
        consider gentler practices like breath awareness first. Always consult with a mental health 
        professional for anxiety disorders.""",
        "title": "Common Questions About Third Eye Meditation",
        "source": "pdf",
        "page": 42,
        "section": "qa"
    },
    
    # Additional Practices
    {
        "content": """BREATH AWARENESS for Third Eye Activation
        
        This gentle technique is suitable for beginners and can be practiced daily.
        
        Instructions:
        1. Sit comfortably with eyes closed
        2. Bring attention to the space between your eyebrows
        3. Breathe naturally through your nose
        4. With each inhale, imagine breath flowing to the Third Eye point
        5. With each exhale, imagine tension releasing from this area
        6. Continue for 10-15 minutes
        
        Variations:
        - Add a mantra like "OM" on each exhale
        - Visualize an indigo sphere of light at the Third Eye
        - Combine with alternate nostril breathing (Nadi Shodhana)
        
        Benefits:
        - Calms the nervous system
        - Improves focus and concentration
        - Gentle stimulation of Ajna chakra
        - Reduces mental chatter
        
        This practice is safe for most people and can be done daily.""",
        "title": "Breath Awareness for Third Eye",
        "source": "pdf",
        "page": 28,
        "section": "practices"
    }
]


async def seed_knowledge():
    """Seed the vector store with sample documents"""
    try:
        logger.info("Starting knowledge base seeding...")
        
        # Upsert documents
        result = await vector_store.upsert_documents(
            documents=SAMPLE_DOCUMENTS,
            doc_id="seed_knowledge_base",
            version=1
        )
        
        logger.info(f"Successfully seeded {result['success_count']} documents")
        print(f"✅ Seeded {result['success_count']} documents to knowledge base")
        print(f"   Doc ID: {result['doc_id']}")
        print(f"   Version: {result['version']}")
        
    except Exception as e:
        logger.error(f"Error seeding knowledge base: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🌱 Seeding Third Eye Meditation knowledge base...")
    asyncio.run(seed_knowledge())
    print("✨ Done!")