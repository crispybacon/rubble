#!/usr/bin/env python3
"""
Unit tests for the static website HTML and CSS
"""

import unittest
import os
import re
from pathlib import Path

class TestStaticWebsite(unittest.TestCase):
    """Test cases for static website HTML and CSS."""

    def setUp(self):
        """Set up test fixtures."""
        self.html_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'content' / 'index.html'
        self.css_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'content' / 'index.css'
        
        # Read the HTML and CSS files
        with open(self.html_path, 'r') as f:
            self.html_content = f.read()
        
        with open(self.css_path, 'r') as f:
            self.css_content = f.read()

    def test_work_experience_minimized_by_default(self):
        """Test that work experience items are minimized by default."""
        # Check if the JavaScript initializes work experience items as collapsed
        self.assertIn("// Initialize all items as collapsed by default", self.html_content)
        self.assertIn("jobContent.classList.add('collapsed')", self.html_content)
        self.assertIn("item.style.paddingBottom = '0.2cm'", self.html_content)

    def test_no_trailing_line_for_last_experience_item(self):
        """Test that there is no trailing line below the bullet point for the final experience item."""
        # Check if the CSS has a rule for the last work experience item
        self.assertIn(".workExperience>ul>li:last-child:before", self.css_content)
        
        # Check if the rule sets the bottom property to stop at the bullet point
        last_item_rule = re.search(r'\.workExperience>ul>li:last-child:before\s*{[^}]*}', self.css_content)
        self.assertIsNotNone(last_item_rule, "Last item rule not found in CSS")
        
        # Check if the bottom property is set to stop at the bullet point
        bottom_property = re.search(r'bottom:\s*0\.1cm', last_item_rule.group(0))
        self.assertIsNotNone(bottom_property, "Bottom property not set correctly for last item")

if __name__ == '__main__':
    unittest.main()
