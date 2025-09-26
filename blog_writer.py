import os
import json
import re
from datetime import date
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- Configuration & Setup ---
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Master Persona Prompt ---
PERSONA_PROMPT = """
You are a world-class SEO Content Writer and Strategist. Your purpose is to write detailed, high-quality, and valuable long-form articles that are optimized to rank highly on search engines like Google. You are an expert in on-page SEO, keyword research, and a clear understanding of what makes content valuable to a reader. You adhere to principles of E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness). Your voice is authoritative, helpful, and clear. You avoid jargon where possible and always prioritize the reader's understanding. You do not write sales copy; your goal is to provide comprehensive information that answers the user's query and establishes the website as a trusted resource.
"""

# --- Utility Function and Schema Definition ---

def slugify(text):
    """Converts text into a URL-safe slug."""
    text = str(text).lower()
    text = re.sub(r'[^\w\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

metadata_schema = types.Schema(
    type=types.Type.OBJECT,
    properties={
        'title': types.Schema(type=types.Type.STRING, description='A catchy, SEO-friendly title for the blog post.'),
        'description': types.Schema(type=types.Type.STRING, description='A compelling meta description, max 160 characters.'),
        'tags': types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description='An array of 5-10 relevant, SEO-optimized tags.'),
        'imageAlt': types.Schema(type=types.Type.STRING, description='A brief, descriptive alt-text for the article\'s main image.'),
    },
    required=['title', 'description', 'tags', 'imageAlt']
)

# --- Stage 1: Context Ingestion ---

def analyze_site_goal(filepath="my-blog/index.njk"):
    print("Analyzing site goal...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
        prompt = f"Analyze the following Nunjucks template content and summarize the website's primary goal, target audience, and overall topic in one short paragraph.\n\nCONTENT:\n{content}"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt])
        print("✅ Site goal analyzed.")
        return response.text
    except FileNotFoundError:
        print(f"⚠️ Warning: {filepath} not found. Skipping site goal analysis.")
        return "No site goal context available."

def analyze_existing_posts(directory="my-blog/blog/"):
    print("Analyzing existing blog posts...")
    try:
        topics = [fn.replace('.md', '').replace('-', ' ') for fn in os.listdir(directory) if fn.endswith(".md")]
        if not topics:
            print("✅ No existing posts found.")
            return "No existing blog posts to analyze."
        print(f"✅ Found {len(topics)} existing posts.")
        return "The blog already has posts covering these topics: " + ", ".join(topics)
    except FileNotFoundError:
        print(f"⚠️ Warning: {directory} not found. Skipping post analysis.")
        return "No existing post context available."

# --- Stage 2: Strategic Topic Selection ---

def determine_next_article_topic(site_goal, existing_posts_summary):
    print("\n🤖 Performing content gap analysis to determine the next article...")
    strategist_prompt = f"You are an SEO Content Strategist. Your task is to decide on the single best article to write next for a blog.\n\n**Website's Purpose:**\n{site_goal}\n\n**Topics Already Covered (DO NOT SUGGEST THESE):**\n{existing_posts_summary}\n\n**Your Task:**\nBased on the content gap, determine the single most valuable blog post topic to write next. Output only the proposed article title."
    response = client.models.generate_content(model='gemini-2.5-flash', contents=[strategist_prompt])
    chosen_topic = response.text.strip()
    if chosen_topic:
        print(f"✅ Strategy locked. Agent will write about: '{chosen_topic}'")
        return chosen_topic
    else:
        print("⚠️ Could not determine a new topic. Aborting.")
        return None
        
# --- Image Generation Function ---

def generate_and_save_image(prompt, filepath):
    """Generates an image using Imagen and saves it to the specified path."""
    print("  -> Step 3/5: Generating blog post image with Imagen...")
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        response = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9")
        )
        if response.generated_images:
            image_data = response.generated_images[0].image
            image_data.save(filepath)
            print(f"  -> ✅ Image successfully saved to: {filepath}")
        else:
            print("  -> ⚠️ WARNING: Imagen did not return an image.")
    except Exception as e:
        print(f"  -> ❌ ERROR: Failed to generate or save image. Skipping. Error: {e}")

# --- Stage 3: Multi-Step Content & Image Generation ---

def generate_and_save_article(chosen_topic, site_goal, existing_posts_summary):
    print(f"\n🚀 Engaging content engine for topic: '{chosen_topic}'")
    article_draft, metadata = None, None

    # STEP 3a: Generate the raw, unformatted article draft
    print("  -> Step 1/5: Writing article draft...")
    try:
        draft_prompt = f"{PERSONA_PROMPT}\n\n**CONTEXT:**\n- Website Goal: {site_goal}\n- Existing Articles: {existing_posts_summary}\n\n**TASK:**\nWrite a comprehensive, 1500-word article on: \"{chosen_topic}\". Output ONLY the raw text."
        draft_response = client.models.generate_content(model='gemini-2.5-flash', contents=[draft_prompt])
        article_draft = draft_response.text
        print("  -> ✅ Draft completed.")
    except Exception as e:
        print(f"  -> ❌ ERROR: Failed to generate article draft. Skipping. Error: {e}")
        return

    # STEP 3b: Generate structured metadata from the draft
    print("  -> Step 2/5: Generating structured metadata...")
    try:
        metadata_prompt = f"Analyze the following blog post text and generate metadata according to the provided schema.\n---\n{article_draft}\n---"
        metadata_response = client.models.generate_content(
            model='gemini-2.5-flash', contents=[metadata_prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=metadata_schema)
        )
        metadata = json.loads(metadata_response.text)
        print("  -> ✅ Metadata generated.")
    except Exception as e:
        print(f"  -> ❌ ERROR: Failed to generate or parse metadata. Skipping. Error: {e}")
        return
        
    # STEP 3c: Generate and save the image
    title = metadata.get('title', chosen_topic)
    image_alt = metadata.get('imageAlt', 'A relevant image for the article.')
    file_slug = slugify(title)
    
    ## MODIFICATION 2: Changed image save path to be in the root `images/` directory
    image_save_path = f"images/{file_slug}.png"
    
    image_prompt = f"A professional, photorealistic blog post hero image. The image is for an article titled '{title}'. It should visually represent: '{image_alt}'. Widescreen, 16:9 aspect ratio, high detail, cinematic lighting."
    generate_and_save_image(image_prompt, image_save_path)

    # STEP 3d: Format the raw draft into clean Markdown
    print("  -> Step 4/5: Formatting body as Markdown...")
    try:
        formatting_prompt = f"Reformat the following text as attractive, readable Markdown. Add a main H1 title (#), section headings (##), subheadings (###), bullet points, and bolding. Only return the fully formatted Markdown.\n---\n{article_draft}\n---"
        formatted_body_response = client.models.generate_content(model='gemini-2.5-flash', contents=[formatting_prompt])
        formatted_body = formatted_body_response.text
        print("  -> ✅ Body formatted.")
    except Exception as e:
        print(f"  -> ❌ ERROR: Failed to format body text. Skipping. Error: {e}")
        return

    # STEP 3e: Assemble the final file and save
    print("  -> Step 5/5: Assembling and saving file...")
    try:
        permalink = f"/blog/{file_slug}.html"
        image_path_for_md = f"/images/{file_slug}.png"
        today_date = date.today().strftime("%Y-%m-%d")
        
        tags_list = metadata.get('tags', ['uncategorized'])
        
        ## MODIFICATION 1: Ensure 'blog' is always a tag, avoiding duplicates.
        # Use a set for efficient handling of uniqueness, standardize to lowercase.
        tags_set = set(tag.lower() for tag in tags_list)
        tags_set.add("blog")
        final_tags_list = sorted(list(tags_set)) # Sort for consistent output
        
        tags_yaml_list = "\n".join([f"  - {slugify(tag)}" for tag in final_tags_list])
        keywords_string = ", ".join(final_tags_list)

        front_matter = f"""---
layout: "layout.html"
title: "{title.replace('"', "'")}"
description: "{metadata.get('description', '').replace('"', "'")}"
keywords: "{keywords_string}"
image: "{image_path_for_md}"
imageAlt: "{image_alt.replace('"', "'")}"
permalink: "{permalink}"
date: "{today_date}"
tags:
{tags_yaml_list}
---
"""
        final_content = front_matter + "\n" + formatted_body
        filename = f"my-blog/blog/{file_slug}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        print(f"\n🎉 Success! New article and image created. File saved as: {filename}")
    except Exception as e:
        print(f"  -> ❌ ERROR: Failed to assemble or save the final file. Error: {e}")

# --- Main Execution Block ---

if __name__ == "__main__":
    site_goal_summary = analyze_site_goal()
    existing_posts_summary = analyze_existing_posts()
    next_topic = determine_next_article_topic(site_goal_summary, existing_posts_summary)
    
    if next_topic:
        generate_and_save_article(next_topic, site_goal_summary, existing_posts_summary)
    else:
        print("\nProcess halted. Agent could not decide on a topic.")