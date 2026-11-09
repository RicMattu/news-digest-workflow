#!/usr/bin/env python3
"""
News Digest Workflow - Versione 2
Legge feed RSS, filtra, riassume e prepara email con audio podcast.
"""

import os
import re
import yaml
import feedparser
import base64
from datetime import datetime
from gtts import gTTS
import tempfile
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NewsDigestWorkflow:
    """Main workflow class"""

    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize with configuration"""
        self.config = self._load_config(config_path)
        self.temp_dir = tempfile.mkdtemp(prefix='news_digest_')
        logger.info(f"Temp directory: {self.temp_dir}")

    def _load_config(self, config_path: str) -> Dict:
        """Load YAML configuration"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise

    def run(self) -> Dict[str, Any]:
        """Main workflow execution"""
        logger.info("Starting News Digest Workflow")

        try:
            # Step 1: Fetch all news
            all_news = self._fetch_all_news()
            logger.info(f"Fetched {len(all_news)} total articles")

            # Step 2: Filter and categorize news
            filtered_news = self._filter_and_categorize(all_news)
            logger.info(f"Filtered to {len(filtered_news)} relevant articles")

            # Step 3: Generate digests per category
            digests = self._generate_digests(filtered_news)
            logger.info(f"Generated {len(digests)} digests")

            # Step 4: Generate audio for each digest
            audio_files = self._generate_audio_digests(digests)
            logger.info(f"Generated {len(audio_files)} audio files")

            # Step 5: Prepare email data
            email_data = self._prepare_email(digests, audio_files)

            return {
                'status': 'success',
                'digests': digests,
                'audio_files': audio_files,
                'email': email_data
            }

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }

    def _fetch_all_news(self) -> List[Dict]:
        """Fetch news from all configured sources"""
        all_news = []

        for source_name, source_config in self.config['news_sources'].items():
            try:
                logger.info(f"Fetching news from {source_config['name']}")
                articles = self._fetch_source_news(source_name, source_config)
                all_news.extend(articles)
                logger.info(f"  -> {len(articles)} articles from {source_config['name']}")
            except Exception as e:
                logger.error(f"Error fetching {source_config['name']}: {e}")
                continue

        return all_news

    def _fetch_source_news(self, source_name: str, source_config: Dict) -> List[Dict]:
        """Fetch news from a single source"""
        url = source_config['url']
        max_articles = source_config.get('max_articles', 5)

        # Special handling for HackerNews
        if source_name == 'hackernews':
            return self._fetch_hackernews(max_articles)

        # Fetch RSS feed
        feed = feedparser.parse(url)

        articles = []
        for entry in feed.entries[:max_articles]:
            article = {
                'source': source_config['name'],
                'title': entry.get('title', 'No title'),
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'summary': entry.get('summary', entry.get('description', '')),
                'content': entry.get('content', [{}])[0].get('value', ''),
                'language': source_config.get('language', 'it'),
                'category': source_config.get('category', 'general')
            }
            articles.append(article)

        return articles

    def _fetch_hackernews(self, max_articles: int = 10) -> List[Dict]:
        """Fetch and filter HackerNews articles"""
        url = "https://hnrss.org/newest"
        feed = feedparser.parse(url)

        articles = []
        for entry in feed.entries[:max_articles * 3]:
            # Skip non-story items
            if 'Ask HN' in entry.get('title', '') or \
               'Show HN' in entry.get('title', '') or \
               'Launch HN' in entry.get('title', ''):
                continue

            article = {
                'source': 'HackerNews',
                'title': entry.get('title', 'No title'),
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'summary': entry.get('summary', ''),
                'content': '',
                'language': 'en',
                'category': 'tecnologia',
                'hn_score': entry.get('hn_score', 0),
                'hn_comments': entry.get('hn_comments', 0)
            }
            articles.append(article)

        return articles[:max_articles]

    def _filter_and_categorize(self, articles: List[Dict]) -> List[Dict]:
        """Filter articles based on configuration and categorize them"""
        filtered = []

        for article in articles:
            source_name = article['source'].lower()
            source_config = None

            # Find source config
            for name, config in self.config['news_sources'].items():
                config_name = config.get('name', '').lower()
                if config_name == source_name:
                    source_config = config
                    break

            if not source_config:
                # Try to match by key
                for name, config in self.config['news_sources'].items():
                    if name.lower() == source_name.replace(' ', '_'):
                        source_config = config
                        break

            if not source_config:
                logger.warning(f"No config found for source: {article['source']}")
                continue

            # Apply filters for HackerNews
            if source_name == 'hackernews':
                if not self._is_hackernews_relevant(article):
                    continue

            # Add category from config
            article['category'] = source_config.get('category', 'general')
            filtered.append(article)

        return filtered

    def _is_hackernews_relevant(self, article: Dict) -> bool:
        """Check if HackerNews article is relevant (AI/Time Series)"""
        title = article['title'].lower()
        summary = article.get('summary', '').lower()
        content = article.get('content', '').lower()

        include_keywords = [
            'time series', 'time-series', 'timeseries',
            'ai', 'artificial intelligence',
            'machine learning', 'deep learning',
            'neural network', 'llm', 'large language model',
            'transformer', 'bert', 'gpt',
            'data science', 'statistics', 'forecasting',
            'temporal', 'sequence', 'recurrent'
        ]

        text_to_check = f"{title} {summary} {content}"

        for keyword in include_keywords:
            if keyword in text_to_check:
                return True

        return False

    def _generate_digests(self, articles: List[Dict]) -> List[Dict]:
        """Generate text digests per category"""
        categories = {}
        for article in articles:
            category = article['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(article)

        digests = []

        for category, category_articles in categories.items():
            # Sort by source importance
            source_order = {
                'corriere della sera': 0,
                'la repubblica': 1,
                'il messaggero': 2,
                'la stampa': 3,
                'l unione sarda': 4,
                'la nuova sardegna': 5,
                'the times': 6,
                'hackernews': 7
            }

            category_articles.sort(
                key=lambda x: source_order.get(x['source'].lower(), 99)
            )

            digest_text = self._generate_category_digest(category, category_articles)

            digests.append({
                'category': category,
                'articles': category_articles,
                'text': digest_text,
                'language': category_articles[0]['language'] if category_articles else 'it'
            })

        return digests

    def _generate_category_digest(self, category: str, articles: List[Dict]) -> str:
        """Generate a text digest for a category"""
        category_names = {
            'nazionale': '🇮🇹 Nazionali',
            'sardo': '🏝️ Sardi',
            'internazionale': '🌍 Internazionali',
            'tecnologia': '💻 Tecnologia (HackerNews)'
        }

        category_display = category_names.get(category, category.capitalize())

        digest_lines = [
            f"{'='*60}",
            f"{category_display}",
            f"{'='*60}",
            ""
        ]

        for i, article in enumerate(articles, 1):
            title = article['title'].replace('&quot;', '"').replace('&amp;', '&')

            source_line = f"📰 {article['source']}"
            if article.get('published'):
                try:
                    published = datetime.strptime(
                        article['published'][:19],
                        '%a, %d %b %Y %H:%M:%S'
                    ).strftime('%d/%m/%Y %H:%M')
                    source_line += f" - {published}"
                except:
                    pass

            digest_lines.extend([
                f"{i}. {title}",
                f"   {source_line}",
                f"   🔗 {article['link']}",
                ""
            ])

            if article.get('summary'):
                summary = article['summary'].strip()
                if summary and len(summary) > 20:
                    summary = summary[:200] + "..." if len(summary) > 200 else summary
                    digest_lines.append(f"   📝 {summary}")
                    digest_lines.append("")

        return "\n".join(digest_lines)

    def _generate_audio_digests(self, digests: List[Dict]) -> List[Dict]:
        """Generate audio files for each digest using gTTS"""
        audio_files = []

        for digest in digests:
            try:
                text = self._prepare_text_for_tts(digest['text'], digest['language'])
                tts_lang = 'it' if digest['language'] == 'it' else 'en'

                tts = gTTS(
                    text=text,
                    lang=tts_lang,
                    slow=False,
                    tld='com'
                )

                audio_path = os.path.join(
                    self.temp_dir,
                    f"digest_{digest['category']}.mp3"
                )
                tts.save(audio_path)

                audio_files.append({
                    'category': digest['category'],
                    'path': audio_path,
                    'language': digest['language']
                })

                logger.info(f"Generated audio for {digest['category']}")

            except Exception as e:
                logger.error(f"Error generating audio for {digest['category']}: {e}")
                continue

        return audio_files

    def _prepare_text_for_tts(self, text: str, language: str) -> str:
        """Prepare text for TTS (remove special chars, format properly)"""
        text = re.sub(r'[#*_~`]', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)

        max_length = 5000
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text.strip()

    def _prepare_email(self, digests: List[Dict], audio_files: List[Dict]) -> Dict:
        """Prepare email data for Gmail connector"""
        email_body_parts = []
        email_body_parts.append("="*60)
        email_body_parts.append("NEWS DIGEST - Riassunto quotidiano")
        email_body_parts.append("="*60)
        email_body_parts.append("")
        email_body_parts.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        email_body_parts.append("")

        for digest in digests:
            email_body_parts.append(digest['text'])
            email_body_parts.append("")

        email_body = "\n".join(email_body_parts)

        attachments = []
        for audio in audio_files:
            try:
                with open(audio['path'], 'rb') as f:
                    audio_data = f.read()
                attachments.append({
                    'filename': f"podcast_{audio['category']}.mp3",
                    'content': base64.b64encode(audio_data).decode('utf-8'),
                    'mimeType': 'audio/mpeg'
                })
                logger.info(f"Prepared attachment for {audio['category']}")
            except Exception as e:
                logger.error(f"Error preparing attachment {audio['category']}: {e}")
                continue

        return {
            'to': [self.config['email']['recipient']],
            'subject': f"{self.config['email']['subject_prefix']} - {datetime.now().strftime('%d/%m/%Y')}",
            'body': email_body,
            'attachments': attachments
        }

def main():
    """Main entry point for CLI execution"""
    workflow = NewsDigestWorkflow()
    result = workflow.run()

    if os.environ.get('MISTRAL_CLOUD') == 'true':
        return result

    print("\n" + "="*60)
    print("WORKFLOW RESULT")
    print("="*60)
    print(f"Status: {result.get('status')}")

    if result.get('status') == 'success':
        print(f"Generated {len(result.get('digests', []))} digests")
        print(f"Generated {len(result.get('audio_files', []))} audio files")
        if 'email' in result:
            print("Email data prepared (ready to send via Gmail connector)")

if __name__ == '__main__':
    main()
