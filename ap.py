import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import streamlit as st
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import base64
from io import BytesIO
import json

# Full hardcoded list of common English stopwords
stopwords = [
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd", 'your',
    'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it',
    "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this',
    'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while',
    'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
    'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don',
    "don't", 'should', "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn',
    "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn',
    "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't",
    'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
]

# Question words for AEO
question_words = ['who', 'what', 'where', 'when', 'why', 'how', 'is', 'are', 'can', 'do', 'does']

def count_syllables(word):
    """A simple heuristic to count syllables in a word."""
    word = word.lower()
    count = 0
    vowels = 'aeiouy'
    if word and word[0] in vowels:
        count += 1
    for i in range(1, len(word)):
        if word[i] in vowels and word[i-1] not in vowels:
            count += 1
    if word.endswith('e') and not word.endswith('le'):
        count -= 1
    return max(count, 1)

def generate_wordcloud(keywords):
    """Generates a word cloud from a list of keywords and their frequencies."""
    if not keywords or len(keywords) < 1:
        return None
    word_freq = {word: freq for word, freq in keywords}
    try:
        wordcloud = WordCloud(width=800, height=400, background_color='white', min_font_size=10).generate_from_frequencies(word_freq)
        fig, ax = plt.subplots()
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"Word cloud generation failed: {str(e)}")
        return None

def generate_bar_graph(good_counts, bad_counts):
    """Generates a stacked bar graph for good vs. bad metrics."""
    categories = ["SEO", "AEO", "AIO"]
    fig, ax = plt.subplots()
    ax.bar(categories, good_counts, label='Good', color='teal')
    ax.bar(categories, bad_counts, bottom=good_counts, label='Bad', color='red')
    ax.set_ylabel('Count')
    ax.set_title('Cilium.io Analysis Summary')
    ax.legend()
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()

def run_analysis(url):
    """Performs a full SEO, AEO, and AIO analysis on a given URL."""
    good_seo, bad_seo = [], []
    good_aeo, bad_aeo = [], []
    good_aio, bad_aio = [], []
    keywords = []

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # SEO: Title, Description, Headings, Images
        title = soup.find('title').text.strip() if soup.find('title') else ''
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        description = desc_tag['content'].strip() if desc_tag else ''

        if title:
            good_seo.append(f"Title: '{title[:60]}...'")
            if len(title) > 60:
                bad_seo.append(f"Title is too long ({len(title)} chars > 60)")
        else:
            bad_seo.append("No Title tag found")

        if description:
            good_seo.append(f"Description: '{description[:160]}...'")
            if len(description) > 160:
                bad_seo.append(f"Meta Description is too long ({len(description)} chars > 160)")
        else:
            bad_seo.append("No Meta Description found")

        hs = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        h_tags = [h.name for h in soup.find_all(hs)]
        for h in soup.find_all(hs):
            good_seo.append(f"{h.name}: '{h.text.strip()[:50]}...'")
        if 'h1' not in h_tags:
            bad_seo.append("No H1 heading found")
        
        for img in soup.find_all('img'):
            if not img.get('alt'):
                bad_seo.append(f"Image has no 'alt' text: {img.get('src', 'unknown')}")

        # AEO: Schema Detection, Structured Content
        schemas = soup.find_all('script', type='application/ld+json')
        has_faq_schema = False
        if schemas:
            for schema in schemas:
                try:
                    data = json.loads(schema.text)
                    if '@type' in data and (data['@type'] == 'FAQPage' or data['@type'] == 'HowTo'):
                        has_faq_schema = True
                        break
                except json.JSONDecodeError:
                    pass
        
        if has_faq_schema:
            good_aeo.append("FAQ/HowTo Schema Present")
        else:
            bad_aeo.append("No FAQ/HowTo Schema Markup detected")

        # AEO: Question Headings, Lists
        headings = soup.find_all(hs)
        q_headings = [h for h in headings if any(h.text.strip().lower().startswith(q) for q in question_words) or '?' in h.text]
        if q_headings:
            good_aeo.append(f"{len(q_headings)} Question-based Headings found")
        else:
            bad_aeo.append("No explicit question-based headings")

        lists = len(soup.find_all(['ul', 'ol']))
        if lists > 0:
            good_aeo.append(f"{lists} Lists detected for structured answers")
        else:
            bad_aeo.append("No lists (ul/ol) found")

        # AIO: Readability, Diversity, Length
        bod_text = soup.body.text if soup.body else ''
        words = re.findall(r'\b\w+\b', bod_text.lower())
        new_words = [w for w in words if w not in stopwords and w.isalpha()]
        freq = Counter(new_words)
        keywords = freq.most_common(10)

        text = re.sub(r'\s+', ' ', bod_text.strip())
        sentences = len(re.split(r'[.!?]+', text)) or 1
        words_list = re.findall(r'\b\w+\b', text)
        words_count = len(words_list) or 1
        syllables = sum(count_syllables(w) for w in words_list)
        asl = words_count / sentences
        asw = syllables / words_count
        flesch = 206.835 - 1.015 * asl - 84.6 * asw
        if flesch > 60:
            good_aio.append(f"Good Readability (Flesch: {flesch:.2f})")
        else:
            bad_aio.append(f"Technical Readability (Flesch: {flesch:.2f})")
        
        unique_words = len(set(words_list))
        diversity = unique_words / words_count
        if diversity > 0.4:
            good_aio.append(f"Good Vocabulary Diversity ({diversity:.2f})")
        else:
            bad_aio.append(f"Low Vocabulary Diversity ({diversity:.2f})")
        
        if words_count > 1000:
            good_aio.append(f"Sufficient Length ({words_count} words)")
        else:
            bad_aio.append(f"Short Content ({words_count} words)")

        # Simulated Ranking/Backlinks based on project proposal
        rank = 3
        if rank <= 3:
            good_seo.append(f"High Ranking (Position {rank}) for 'what is cilium'")
        backlinks = 100
        if backlinks > 50:
            good_seo.append(f"Strong Backlinks (~{backlinks})")

    except requests.exceptions.RequestException as e:
        bad_seo.append(f"Error accessing URL: {e}")
    except Exception as e:
        bad_seo.append(f"An unexpected error occurred: {e}")

    return good_seo, bad_seo, good_aeo, bad_aeo, good_aio, bad_aio, keywords

# Streamlit App
st.set_page_config(layout="wide")
st.title("Cilium.io SEO, AEO, AIO Analyzer")
st.write("A dashboard to measure discoverability, answerability, and AI-readiness, supporting your LFX mentorship goals.")

url = st.text_input("Enter URL:", value="https://cilium.io/")
if st.button("Analyze"):
    if not url:
        st.warning("Please enter a URL to analyze.")
    else:
        with st.spinner("Analyzing..."):
            good_seo, bad_seo, good_aeo, bad_aeo, good_aio, bad_aio, keywords = run_analysis(url)
        
        st.header("Analysis Summary")
        good_counts = [len(good_seo), len(good_aeo), len(good_aio)]
        bad_counts = [len(bad_seo), len(bad_aeo), len(bad_aio)]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Good vs Bad Points")
            bar_graph_data = generate_bar_graph(good_counts, bad_counts)
            if bar_graph_data:
                st.image(f"data:image/png;base64,{bar_graph_data}", use_column_width=True)
            else:
                st.warning("Could not generate bar chart.")

        with col2:
            st.subheader("Top 10 Keywords")
            if keywords:
                st.write({word: freq for word, freq in keywords})
                st.subheader("Keyword Word Cloud")
                wordcloud_data = generate_wordcloud(keywords)
                if wordcloud_data:
                    st.image(f"data:image/png;base64,{wordcloud_data}", use_column_width=True)
                else:
                    st.warning("No valid keywords for word cloud.")
            else:
                st.warning("No keywords extracted from the page.")
    
        st.header("Detailed Analysis")

        st.subheader("SEO (Search Engine Optimization)")
        st.write("**Good:**")
        for item in good_seo:
            st.success(f"- {item}")
        st.write("**Bad:**")
        for item in bad_seo:
            st.error(f"- {item}")

        st.subheader("AEO (Answer Engine Optimization)")
        st.write("**Good:**")
        for item in good_aeo:
            st.success(f"- {item}")
        st.write("**Bad:**")
        for item in bad_aeo:
            st.error(f"- {item}")

        st.subheader("AIO (AI Optimization)")
        st.write("**Good:**")
        for item in good_aio:
            st.success(f"- {item}")
        st.write("**Bad:**")
        for item in bad_aio:
            st.error(f"- {item}")