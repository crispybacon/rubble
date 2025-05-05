#!/usr/bin/env python3
"""
Test script for mailto functionality in the contact form
"""

import unittest
import os
import sys
import re
import yaml
from pathlib import Path

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMailtoFunctionality(unittest.TestCase):
    """Test class for mailto functionality in the contact form"""

    def setUp(self):
        """Set up test environment"""
        # Path to the index.html file
        self.index_path = Path('iac/static_website/index.html')
        
        # Path to the config.yaml file
        self.config_path = Path('config.yaml')
        
        # Load the config file
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Get the email address from the config
        self.email_address = self.config['messaging']['email']['destination']
        
        # Load the index.html file
        with open(self.index_path, 'r') as f:
            self.html_content = f.read()

    def test_email_address_in_config(self):
        """Test that the email address is defined in the config file"""
        self.assertIsNotNone(self.email_address)
        self.assertTrue('@' in self.email_address)
        self.assertEqual(self.email_address, 'jesse.bacon@flatstoneservices.com')

    def test_email_address_in_javascript(self):
        """Test that the email address is hardcoded in the JavaScript code"""
        # Check for the hardcoded email address in the JavaScript code
        email_pattern = r"const\s+emailAddress\s*=\s*'jesse\.bacon@flatstoneservices\.com';"
        self.assertTrue(re.search(email_pattern, self.html_content))
        
    def test_mailto_link_in_javascript(self):
        """Test that the mailto link is implemented in the JavaScript code"""
        # Check for the mailto link in the JavaScript code
        mailto_pattern = r"window\.location\.href\s*=\s*`mailto:\${emailAddress}\?subject=.*`"
        self.assertTrue(re.search(mailto_pattern, self.html_content))

    def test_email_popup_message(self):
        """Test that a popup message is shown to the user"""
        # Check for the popup message
        popup_pattern = r"I can be reached at the email address:"
        self.assertTrue(re.search(popup_pattern, self.html_content))
        
        # Check that the email address is displayed in the popup
        email_display_pattern = r"<p><strong>\${emailAddress}</strong></p>"
        self.assertTrue(re.search(email_display_pattern, self.html_content))
        
    def test_email_button_exists(self):
        """Test that the email button exists in the popup"""
        # Check for the email button
        button_pattern = r'<button type="button" class="submit-btn" id="open-email-btn">Open Email Client</button>'
        self.assertTrue(re.search(button_pattern, self.html_content))
        
        # Check for the button click handler
        click_handler_pattern = r"emailBtn\.addEventListener\('click', function\(\) \{\s*window\.location\.href = `mailto:\${emailAddress}\?subject=.*`;"
        self.assertTrue(re.search(click_handler_pattern, self.html_content))
        
    def test_email_popup_styling(self):
        """Test that the email popup uses the proper CSS classes for styling"""
        # Check that the email popup has the custom-alert class
        popup_class_pattern = r"emailPopup\.className = 'custom-alert'"
        self.assertTrue(re.search(popup_class_pattern, self.html_content))
        
        # Check that the content div has the alert-content class
        content_class_pattern = r'<div class="alert-content">'
        self.assertTrue(re.search(content_class_pattern, self.html_content))
        
        # Check that the header has the alert-header class
        header_class_pattern = r'<div class="alert-header">'
        self.assertTrue(re.search(header_class_pattern, self.html_content))
        
        # Check that the body has the alert-body class
        body_class_pattern = r'<div class="alert-body">'
        self.assertTrue(re.search(body_class_pattern, self.html_content))
        
        # Check that the button has the submit-btn class
        button_class_pattern = r'<button type="button" class="submit-btn" id="open-email-btn">'
        self.assertTrue(re.search(button_class_pattern, self.html_content))
        
        # Load the CSS file to check for the required styles
        css_path = Path('iac/static_website/index.css')
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check that the CSS file contains the required styles
        self.assertIn('.custom-alert', css_content)
        self.assertIn('.alert-content', css_content)
        self.assertIn('.alert-header', css_content)
        self.assertIn('.alert-body', css_content)
        self.assertIn('.submit-btn', css_content)

    def test_auto_close_popup(self):
        """Test that the popup auto-closes after a delay"""
        # Check for the auto-close functionality
        auto_close_pattern = r"setTimeout\(\(\)\s*=>\s*\{\s*if\s*\(document\.body\.contains\(emailPopup\)\)\s*\{\s*document\.body\.removeChild\(emailPopup\);\s*\}\s*\},\s*\d+\);"
        self.assertTrue(re.search(auto_close_pattern, self.html_content))

    def test_sms_form_still_exists(self):
        """Test that the SMS form still exists and works"""
        # Check that the SMS form still exists
        sms_form_pattern = r'<form id="sms-form">'
        self.assertTrue(re.search(sms_form_pattern, self.html_content))
        
        # Check that the SMS form has the required fields
        name_field_pattern = r'<input type="text" id="name" name="name" required>'
        message_field_pattern = r'<textarea id="message" name="message" rows="5" required></textarea>'
        
        self.assertTrue(re.search(name_field_pattern, self.html_content))
        self.assertTrue(re.search(message_field_pattern, self.html_content))


if __name__ == "__main__":
    unittest.main()