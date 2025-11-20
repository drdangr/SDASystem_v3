"""
Mock data generator for testing SDASystem
Generates news, actors, and relationships for multiple story clusters
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict
import random

from backend.models.entities import (
    News, Actor, ActorType, ActorRelation, RelationType, DomainCategory
)


class MockDataGenerator:
    """Generate mock data for testing"""

    def __init__(self):
        self.actors: List[Actor] = []
        self.news: List[News] = []
        self.actor_id_map: Dict[str, str] = {}

    def generate_full_dataset(self) -> Dict:
        """Generate complete mock dataset with multiple stories"""
        # Create actors
        self._generate_actors()

        # Generate news for different story clusters
        self._generate_ai_regulation_story()
        self._generate_ukraine_conflict_story()
        self._generate_climate_summit_story()
        self._generate_tech_merger_story()
        self._generate_election_story()

        return {
            "actors": [actor.model_dump() for actor in self.actors],
            "news": [news.model_dump() for news in self.news]
        }

    def _generate_actors(self):
        """Create a set of actors (politicians, companies, countries, etc.)"""

        actors_data = [
            # Politicians
            ("Vladimir Putin", ActorType.PERSON, ["Путин", "Putin", "President Putin"]),
            ("Joe Biden", ActorType.PERSON, ["Biden", "President Biden", "Байден"]),
            ("Xi Jinping", ActorType.PERSON, ["Xi", "Си Цзиньпин"]),
            ("Ursula von der Leyen", ActorType.PERSON, ["von der Leyen", "фон дер Ляйен"]),
            ("Volodymyr Zelensky", ActorType.PERSON, ["Zelensky", "Зеленский"]),

            # Companies
            ("OpenAI", ActorType.COMPANY, ["OpenAI Inc", "ChatGPT maker"]),
            ("Google", ActorType.COMPANY, ["Alphabet", "Google Inc"]),
            ("Microsoft", ActorType.COMPANY, ["MSFT", "Microsoft Corp"]),
            ("Tesla", ActorType.COMPANY, ["Tesla Inc", "TSLA"]),
            ("Meta", ActorType.COMPANY, ["Facebook", "Meta Platforms"]),

            # Countries
            ("United States", ActorType.COUNTRY, ["USA", "US", "America", "США"]),
            ("Russia", ActorType.COUNTRY, ["Russian Federation", "Россия"]),
            ("China", ActorType.COUNTRY, ["PRC", "Китай"]),
            ("European Union", ActorType.ORGANIZATION, ["EU", "ЕС"]),
            ("Ukraine", ActorType.COUNTRY, ["Украина"]),

            # Organizations
            ("United Nations", ActorType.ORGANIZATION, ["UN", "ООН"]),
            ("NATO", ActorType.ORGANIZATION, ["North Atlantic Treaty Organization"]),
            ("European Commission", ActorType.ORGANIZATION, ["EC", "Еврокомиссия"]),
            ("World Health Organization", ActorType.ORGANIZATION, ["WHO", "ВОЗ"]),
        ]

        for canonical_name, actor_type, aliases in actors_data:
            actor_id = f"actor_{uuid.uuid4().hex[:12]}"
            actor = Actor(
                id=actor_id,
                canonical_name=canonical_name,
                actor_type=actor_type,
                aliases=[{"name": alias, "type": "alias"} for alias in aliases]
            )
            self.actors.append(actor)
            self.actor_id_map[canonical_name] = actor_id

    def _create_news(
        self,
        title: str,
        summary: str,
        full_text: str,
        actors: List[str],
        domains: List[str],
        days_ago: int = 0,
        source: str = "News Agency"
    ) -> News:
        """Helper to create a news item"""
        news_id = f"news_{uuid.uuid4().hex[:12]}"
        published_at = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23))

        # Map actor names to IDs
        actor_ids = [self.actor_id_map[name] for name in actors if name in self.actor_id_map]

        news = News(
            id=news_id,
            title=title,
            summary=summary,
            full_text=full_text,
            source=source,
            published_at=published_at,
            mentioned_actors=actor_ids,
            domains=domains
        )

        self.news.append(news)
        return news

    def _generate_ai_regulation_story(self):
        """Generate news cluster about AI regulation"""
        domain = ["Technology", "AI", "Regulation", "Politics"]

        self._create_news(
            title="EU Announces New AI Regulation Framework",
            summary="European Union introduces comprehensive AI safety regulations requiring transparency and risk assessment.",
            full_text="The European Commission announced today a new framework for artificial intelligence regulation. Ursula von der Leyen stated that the regulations will ensure AI systems are safe and respect fundamental rights. The framework includes mandatory risk assessments for high-risk AI applications.",
            actors=["European Union", "Ursula von der Leyen", "European Commission"],
            domains=domain,
            days_ago=1
        )

        self._create_news(
            title="OpenAI Responds to EU AI Regulations",
            summary="OpenAI announces compliance plan with new European AI safety requirements.",
            full_text="OpenAI announced plans to comply with the new EU AI regulations. The company will implement additional safety measures and transparency requirements for ChatGPT and other AI systems operating in European markets.",
            actors=["OpenAI", "European Union"],
            domains=domain,
            days_ago=2
        )

        self._create_news(
            title="US Considers Similar AI Safety Framework",
            summary="Following EU's lead, United States debates implementing AI oversight regulations.",
            full_text="Joe Biden administration is considering implementing AI safety regulations similar to those announced by the European Union. Tech companies including Microsoft and Google have expressed support for responsible AI governance.",
            actors=["United States", "Joe Biden", "Microsoft", "Google"],
            domains=domain,
            days_ago=3
        )

        self._create_news(
            title="Tech Giants Form AI Safety Alliance",
            summary="Major technology companies create coalition to develop AI safety standards.",
            full_text="OpenAI, Microsoft, Google, and Meta announced the formation of an AI Safety Alliance to develop industry standards for artificial intelligence. The initiative comes in response to increasing regulatory pressure from governments worldwide.",
            actors=["OpenAI", "Microsoft", "Google", "Meta"],
            domains=domain,
            days_ago=4
        )

    def _generate_ukraine_conflict_story(self):
        """Generate news cluster about Ukraine conflict"""
        domain = ["Politics", "Military", "International Relations", "Ukraine Conflict"]

        self._create_news(
            title="NATO Announces Additional Military Aid to Ukraine",
            summary="NATO members agree to provide additional military equipment and training to Ukrainian forces.",
            full_text="NATO announced today an expanded military support package for Ukraine. Volodymyr Zelensky thanked alliance members for their continued support. The package includes advanced defense systems and training programs.",
            actors=["NATO", "Ukraine", "Volodymyr Zelensky"],
            domains=domain,
            days_ago=0
        )

        self._create_news(
            title="Russia Criticizes NATO Expansion Plans",
            summary="Russian officials condemn NATO's military aid to Ukraine as escalation.",
            full_text="Vladimir Putin criticized NATO's decision to increase military support to Ukraine, calling it an escalation of the conflict. Russia warned of potential consequences for regional security.",
            actors=["Russia", "Vladimir Putin", "NATO", "Ukraine"],
            domains=domain,
            days_ago=1
        )

        self._create_news(
            title="UN Calls for Peace Negotiations",
            summary="United Nations urges diplomatic solution to ongoing Ukraine conflict.",
            full_text="The United Nations called for immediate peace negotiations to resolve the Ukraine conflict. The organization emphasized the humanitarian impact and urged all parties to return to the negotiating table.",
            actors=["United Nations", "Ukraine", "Russia"],
            domains=domain,
            days_ago=2
        )

    def _generate_climate_summit_story(self):
        """Generate news cluster about climate summit"""
        domain = ["Environment", "Climate", "Politics", "International"]

        self._create_news(
            title="Global Climate Summit Opens with Ambitious Goals",
            summary="World leaders gather to discuss climate action and emission reduction targets.",
            full_text="Leaders from around the world gathered today for the global climate summit. Joe Biden, Xi Jinping, and Ursula von der Leyen are among the attendees. The summit aims to establish new emission reduction commitments.",
            actors=["United States", "Joe Biden", "China", "Xi Jinping", "European Union", "Ursula von der Leyen"],
            domains=domain,
            days_ago=1
        )

        self._create_news(
            title="EU Pledges Carbon Neutrality by 2040",
            summary="European Union announces accelerated timeline for achieving carbon neutrality.",
            full_text="The European Union announced an ambitious plan to achieve carbon neutrality by 2040, ten years ahead of the original target. Ursula von der Leyen stated this demonstrates Europe's commitment to climate leadership.",
            actors=["European Union", "Ursula von der Leyen"],
            domains=domain,
            days_ago=2
        )

    def _generate_tech_merger_story(self):
        """Generate news cluster about tech merger"""
        domain = ["Economics", "Technology", "Business", "Mergers"]

        self._create_news(
            title="Microsoft Announces Major AI Investment",
            summary="Microsoft reveals multi-billion dollar investment in AI infrastructure and development.",
            full_text="Microsoft announced a major investment in AI infrastructure, including expanded partnerships with OpenAI. The company plans to integrate advanced AI capabilities across all product lines.",
            actors=["Microsoft", "OpenAI"],
            domains=domain,
            days_ago=5
        )

        self._create_news(
            title="Google Responds with Competing AI Strategy",
            summary="Google unveils comprehensive AI development roadmap to compete with Microsoft.",
            full_text="In response to Microsoft's AI investments, Google announced an accelerated AI development strategy. The company emphasized its long-standing AI research and development capabilities.",
            actors=["Google", "Microsoft"],
            domains=domain,
            days_ago=6
        )

    def _generate_election_story(self):
        """Generate news cluster about elections"""
        domain = ["Politics", "Elections", "United States", "Democracy"]

        self._create_news(
            title="US Presidential Campaign Intensifies",
            summary="Presidential candidates increase campaign activities ahead of upcoming elections.",
            full_text="The United States presidential campaign entered a new phase with candidates intensifying their outreach efforts. Joe Biden outlined his vision for the next term, focusing on economic recovery and international leadership.",
            actors=["United States", "Joe Biden"],
            domains=domain,
            days_ago=3
        )

        self._create_news(
            title="Tech Leaders Discuss Election Security",
            summary="Major technology companies commit to enhanced election security measures.",
            full_text="Leaders from Microsoft, Google, and Meta met to discuss election security and misinformation prevention. The companies committed to implementing enhanced verification and transparency measures.",
            actors=["Microsoft", "Google", "Meta", "United States"],
            domains=domain,
            days_ago=4
        )

    def save_to_file(self, filepath: str):
        """Save generated data to JSON file"""
        data = self.generate_full_dataset()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        print(f"Mock data saved to {filepath}")
        print(f"Generated {len(self.actors)} actors and {len(self.news)} news items")


def generate_mock_data():
    """Main function to generate mock data"""
    generator = MockDataGenerator()
    generator.save_to_file("data/mock_data.json")
    return generator


if __name__ == "__main__":
    generate_mock_data()
