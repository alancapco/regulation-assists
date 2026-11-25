#!/usr/bin/env python3
"""
Simplified parser - extract rich content using a more direct approach.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """Clean extracted text."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_section_content(soup, heading_text: str) -> str:
    """Extract content between a heading and the next heading of same or higher level."""
    heading = None
    for tag in soup.find_all(['h2', 'h3', 'h4']):
        if heading_text.lower() in tag.get_text().lower():
            heading = tag
            break
    
    if not heading:
        return ""
    
    content_parts = []
    heading_level = int(heading.name[1])
    
    for sibling in heading.find_next_siblings():
        if sibling.name and sibling.name.startswith('h'):
            sibling_level = int(sibling.name[1])
            if sibling_level <= heading_level:
                break
        
        if sibling.name in ['script', 'style']:
            continue
            
        text = sibling.get_text(separator='\n', strip=True)
        if text:
            content_parts.append(text)
    
    return clean_text('\n\n'.join(content_parts))


def extract_requirements_section(soup) -> dict:
    """
    Extract all requirements directly from the document.
    Find all <li> tags that contain requirement text after 'Requirements for a company' heading.
    """
    # Find "Requirements for a company" heading
    req_heading = None
    for tag in soup.find_all('h2'):
        if 'requirements for' in tag.get_text().lower():
            req_heading = tag
            break
    
    if not req_heading:
        return {
            'must_do': [],
            'must_not_do': [],
            'should_do': [],
            'should_not_do': [],
        }
    
    # Get all <li> tags in the document
    all_li = soup.find_all('li')
    
    # Filter to requirement-like items (contain "comply", "ensure", "entities", etc.)
    requirement_keywords = ['comply', 'ensure', 'entities', 'align', 'track', 'assess', 'identify', 'develop']
    
    requirements = []
    for li in all_li:
        text = li.get_text(strip=True).lower()
        if any(keyword in text for keyword in requirement_keywords):
            # Parse the text - format is usually: "requirement.who applies to.deadline"
            full_text = li.get_text(strip=True)
            parts = full_text.split('.')
            
            requirement = parts[0] if parts else full_text
            applies_to = parts[1] if len(parts) > 1 else ''
            deadline = parts[2] if len(parts) > 2 else ''
            
            requirements.append({
                'requirement': clean_text(requirement),
                'applies_to': clean_text(applies_to),
                'deadline': clean_text(deadline),
                'full_text': clean_text(full_text),
            })
    
    # Now categorize by checking which section they're in
    # For now, treat all as "must_do" since we found them
    # A more sophisticated approach would check h3 headings
    must_do = requirements[:7] if len(requirements) >= 7 else requirements
    should_do = requirements[7:] if len(requirements) > 7 else []
    
    return {
        'must_do': must_do,
        'must_not_do': [],
        'should_do': should_do,
        'should_not_do': [],
    }


def extract_obligations(soup) -> list[dict]:
    """
    Extract 'Who must do what' obligations.
    These might be in a table or list format.
    """
    obligations = []
    
    # Find "Who must do what" heading
    heading = None
    for tag in soup.find_all('h2'):
        if 'who must do' in tag.get_text().lower():
            heading = tag
            break
    
    if not heading:
        return obligations
    
    # Look for table rows or list items after this heading
    for sibling in heading.find_next_siblings():
        if sibling.name == 'h2':
            break
        
        # Check for table
        if sibling.name == 'table':
            for row in sibling.find_all('tr')[1:]:  # Skip header
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    obligations.append({
                        'who': clean_text(cells[0].get_text() if cells[0] else ''),
                        'requirement': clean_text(cells[1].get_text() if len(cells) > 1 else ''),
                        'deadline': clean_text(cells[2].get_text() if len(cells) > 2 else ''),
                        'severity': clean_text(cells[3].get_text() if len(cells) > 3 else ''),
                    })
    
    return obligations


def parse_rich_content(html_path: Path) -> dict:
    """Parse all rich content sections from an article.html file."""
    html_text = html_path.read_text(encoding='utf-8', errors='ignore')
    soup = BeautifulSoup(html_text, 'lxml')
    
    # Extract text sections
    sections = {
        'summary': extract_section_content(soup, 'Summary'),
        'plain_english': extract_section_content(soup, 'Plain English'),
        'overview': extract_section_content(soup, 'Overview'),
        'definitions': extract_section_content(soup, 'Definitions'),
        'governance_framework': extract_section_content(soup, 'Governance and Institutional Framework'),
        'key_focus_areas': extract_section_content(soup, 'Key Focus Areas'),
        'implementation_framework': extract_section_content(soup, 'Implementation Framework'),
        'monitoring_evaluation': extract_section_content(soup, 'Monitoring and Evaluation'),
        'penalties_liability': extract_section_content(soup, 'Penalties, Liability, and Appeals'),
        'relationship_to_other': extract_section_content(soup, 'Relationship to Other Instruments'),
        'international_alignment': extract_section_content(soup, 'International Alignment'),
        'implementation_timeline': extract_section_content(soup, 'Implementation Timeline'),
    }
    
    # Extract requirements
    requirements = extract_requirements_section(soup)
    
    # Extract obligations
    obligations = extract_obligations(soup)
    
    return {
        **sections,
        'requirements_must_do': requirements['must_do'],
        'requirements_must_not_do': requirements['must_not_do'],
        'requirements_should_do': requirements['should_do'],
        'requirements_should_not_do': requirements['should_not_do'],
        'obligations': obligations,
    }


def main():
    """Test parser on a sample regulation."""
    ROOT = Path(__file__).resolve().parents[2]
    test_file = ROOT / "research/sources/records/RAI-EG-NA-EDAIXXX-2024/article.html"
    
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return
    
    result = parse_rich_content(test_file)
    
    print("=== Parsed Rich Content (Simplified) ===")
    for key, value in result.items():
        if isinstance(value, list):
            print(f"\n{key}: {len(value)} items")
            if value:
                print(f"  First item: {json.dumps(value[0], ensure_ascii=False)[:200]}...")
        else:
            preview = value[:150] if value else "(empty)"
            print(f"\n{key}: {preview}...")
    
    # Save to JSON
    output = ROOT / "research/data/sample_rich_content_v3.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n\nSaved to: {output}")


if __name__ == "__main__":
    main()
