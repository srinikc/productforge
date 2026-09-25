"""
Customer Onboarding
Generates onboarding materials, setup guides, tutorials, and support resources
"""
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any


class OnboardingGenerator:
    """Generates customer onboarding materials"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)

    def generate_onboarding_package(self, product_name: str,
                                    product_data: Dict[str, Any],
                                    customer_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate complete onboarding package"""
        output_dir = self.products_dir / product_name / "onboarding"
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "product": product_name,
            "generated_at": datetime.now().isoformat(),
            "files": {}
        }

        # Generate welcome email
        welcome = self._generate_welcome_email(product_data, customer_data)
        welcome_path = output_dir / "welcome-email.md"
        welcome_path.write_text(welcome, encoding="utf-8")
        results["files"]["welcome_email"] = str(welcome_path)

        # Generate setup checklist
        checklist = self._generate_setup_checklist(product_data)
        checklist_path = output_dir / "setup-checklist.md"
        checklist_path.write_text(checklist, encoding="utf-8")
        results["files"]["setup_checklist"] = str(checklist_path)

        # Generate installation guide
        install = self._generate_installation_guide(product_data)
        install_path = output_dir / "installation-guide.md"
        install_path.write_text(install, encoding="utf-8")
        results["files"]["installation_guide"] = str(install_path)

        # Generate first-run wizard
        wizard = self._generate_first_run_wizard(product_data)
        wizard_path = output_dir / "first-run-wizard.md"
        wizard_path.write_text(wizard, encoding="utf-8")
        results["files"]["first_run_wizard"] = str(wizard_path)

        # Generate quick wins
        quick_wins = self._generate_quick_wins(product_data)
        quick_wins_path = output_dir / "quick-wins.md"
        quick_wins_path.write_text(quick_wins, encoding="utf-8")
        results["files"]["quick_wins"] = str(quick_wins_path)

        # Generate user manual
        manual = self._generate_user_manual(product_data)
        manual_path = output_dir / "user-manual.md"
        manual_path.write_text(manual, encoding="utf-8")
        results["files"]["user_manual"] = str(manual_path)

        # Generate FAQ
        faq = self._generate_faq(product_data)
        faq_path = output_dir / "faq.md"
        faq_path.write_text(faq, encoding="utf-8")
        results["files"]["faq"] = str(faq_path)

        # Generate troubleshooting guide
        troubleshooting = self._generate_troubleshooting(product_data)
        troubleshooting_path = output_dir / "troubleshooting.md"
        troubleshooting_path.write_text(troubleshooting, encoding="utf-8")
        results["files"]["troubleshooting"] = str(troubleshooting_path)

        # Generate support resources
        support = self._generate_support_resources(product_data)
        support_path = output_dir / "support-resources.md"
        support_path.write_text(support, encoding="utf-8")
        results["files"]["support_resources"] = str(support_path)

        # Generate success metrics
        metrics = self._generate_success_metrics()
        metrics_path = output_dir / "success-metrics.md"
        metrics_path.write_text(metrics, encoding="utf-8")
        results["files"]["success_metrics"] = str(metrics_path)

        # Generate communication plan
        comm_plan = self._generate_communication_plan()
        comm_path = output_dir / "communication-plan.md"
        comm_path.write_text(comm_plan, encoding="utf-8")
        results["files"]["communication_plan"] = str(comm_path)

        return results

    def _generate_welcome_email(self, product_data: Dict[str, Any],
                                customer_data: Optional[Dict[str, Any]]) -> str:
        """Generate personalized welcome email"""
        name = product_data.get("name", "Product")
        customer_name = customer_data.get("name", "[Customer Name]") if customer_data else "[Customer Name]"

        return f"""# Welcome to {name}!

**To:** {customer_name}
**From:** Customer Success Team
**Subject:** Welcome to {name} - Let's get you started!

---

Hi {customer_name},

Welcome to {name}! We're thrilled to have you on board.

{product_data.get('description', 'Thank you for choosing our product. We\'re confident it will help you achieve your goals.')}

## What's Next?

To help you get the most out of {name}, we've prepared a personalized onboarding journey:

1. **[Setup Checklist](setup-checklist.md)** - Get your account ready in 10 minutes
2. **[Installation Guide](installation-guide.md)** - Step-by-step installation
3. **[First-Run Wizard](first-run-wizard.md)** - Interactive tutorial
4. **[Quick Wins](quick-wins.md)** - Achieve your first results in 5 minutes

## Need Help?

We're here to support you every step of the way:

- 📚 [Documentation](user-manual.md)
- ❓ [FAQ](faq.md)
- 🔧 [Troubleshooting](troubleshooting.md)
- 💬 [Support Resources](support-resources.md)

## Your Success is Our Success

We've helped thousands of customers achieve their goals with {name}. We're confident you will too.

Let's get started!

Best regards,
The {name} Team
"""

    def _generate_setup_checklist(self, product_data: Dict[str, Any]) -> str:
        """Generate setup checklist"""
        name = product_data.get("name", "Product")

        return f"""# {name} - Setup Checklist

Complete these steps to get your {name} account ready.

## Account Setup
- [ ] Create your account
- [ ] Verify your email address
- [ ] Set up two-factor authentication
- [ ] Choose your username
- [ ] Upload profile picture (optional)

## Initial Configuration
- [ ] Complete your profile
- [ ] Set your preferences
- [ ] Configure notifications
- [ ] Set your timezone
- [ ] Choose your language

## Integration Setup
- [ ] Connect your data sources
- [ ] Configure API keys
- [ ] Set up webhooks
- [ ] Import existing data
- [ ] Run validation tests

## Team Setup
- [ ] Invite team members
- [ ] Assign roles and permissions
- [ ] Create teams/departments
- [ ] Set up approval workflows
- [ ] Configure SSO (if applicable)

## Security & Compliance
- [ ] Review security settings
- [ ] Enable audit logging
- [ ] Configure data retention
- [ ] Set up backup schedule
- [ ] Review compliance requirements

## Final Steps
- [ ] Test all integrations
- [ ] Run end-to-end test
- [ ] Schedule training session
- [ ] Bookmark documentation
- [ ] Join community forum

---

**Estimated time:** 30-45 minutes
**Need help?** Contact support@example.com
"""

    def _generate_installation_guide(self, product_data: Dict[str, Any]) -> str:
        """Generate installation guide"""
        name = product_data.get("name", "Product")
        tech_stack = product_data.get("architecture", {}).get("tech_stack", [])

        return f"""# {name} - Installation Guide

## System Requirements

- **OS:** Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 1GB free space
- **Network:** Broadband internet connection

## Installation Methods

### Method 1: Quick Install (Recommended)

```bash
# Install {name}
pip install {name.lower()}

# Verify installation
{name.lower()} --version
```

### Method 2: Docker

```bash
# Pull the image
docker pull {name.lower()}/latest

# Run the container
docker run -d -p 8080:8080 {name.lower()}/latest
```

### Method 3: Manual Installation

1. Download the latest release from our website
2. Extract the archive
3. Run the installer
4. Follow the setup wizard

## Configuration

After installation, configure {name}:

```bash
# Initialize configuration
{name.lower()} init

# Edit configuration file
nano ~/.{name.lower()}/config.yaml
```

## Verification

Test your installation:

```bash
# Run health check
{name.lower()} health-check

# Expected output: ✓ All systems operational
```

## Next Steps

- [Complete setup checklist](setup-checklist.md)
- [Run first-run wizard](first-run-wizard.md)
- [Try quick wins](quick-wins.md)

## Troubleshooting

If you encounter issues:
- Check [Troubleshooting Guide](troubleshooting.md)
- Contact support@example.com
- Visit our [community forum](support-resources.md)
"""

    def _generate_first_run_wizard(self, product_data: Dict[str, Any]) -> str:
        """Generate first-run wizard"""
        name = product_data.get("name", "Product")

        return f"""# {name} - First-Run Wizard

Welcome! Let's get you up and running in just 5 minutes.

## Step 1: Choose Your Goal (30 seconds)

What do you want to accomplish with {name}?

- [ ] Increase productivity
- [ ] Save time on repetitive tasks
- [ ] Collaborate with my team
- [ ] Analyze data and insights
- [ ] Automate workflows
- [ ] Other: ___________

## Step 2: Quick Tour (1 minute)

Let's take a quick tour of the main features:

### Dashboard
Your command center for everything {name} does.

### Projects
Organize your work and track progress.

### Settings
Customize {name} to fit your needs.

### Help
Access documentation and support.

## Step 3: Create Your First Project (2 minutes)

1. Click "New Project"
2. Choose a template or start from scratch
3. Give it a name
4. Add a description
5. Click "Create"

## Step 4: Add Your Team (1 minute)

Invite team members to collaborate:

1. Click "Team" in the sidebar
2. Click "Invite Members"
3. Enter email addresses
4. Choose roles
5. Send invitations

## Step 5: Explore Quick Wins (30 seconds)

Try these quick wins to see {name} in action:

- [ ] Create a sample project
- [ ] Add a team member
- [ ] Generate your first report
- [ ] Set up a notification
- [ ] Customize your dashboard

## Congratulations! 🎉

You've completed the first-run wizard. You're ready to start using {name}!

### What's Next?

- [Explore advanced features](user-manual.md)
- [Watch video tutorials](support-resources.md)
- [Join the community](support-resources.md)
- [Schedule training](support-resources.md)

### Need Help?

- [FAQ](faq.md)
- [Troubleshooting](troubleshooting.md)
- [Contact Support](support-resources.md)
"""

    def _generate_quick_wins(self, product_data: Dict[str, Any]) -> str:
        """Generate quick wins"""
        name = product_data.get("name", "Product")

        return f"""# {name} - Quick Wins

Achieve these wins in 5 minutes or less to see immediate value.

## ⚡ 5-Minute Wins

### 1. Create Your First Project (2 min)
- Start with a template
- Name it after a real goal
- See the dashboard populate

### 2. Invite a Team Member (1 min)
- Add one colleague
- Assign them a role
- Collaborate in real-time

### 3. Generate a Report (2 min)
- Choose a template
- Customize the data
- Export to PDF or share link

## 🎯 15-Minute Wins

### 4. Set Up Automation
- Choose a trigger
- Define an action
- Watch it work

### 5. Connect Your Data
- Link a data source
- Map your fields
- See insights appear

### 6. Customize Your Dashboard
- Add widgets
- Arrange your layout
- Save your preferences

## 🚀 30-Minute Wins

### 7. Create a Workflow
- Define steps
- Set conditions
- Automate handoffs

### 8. Set Up Notifications
- Choose what to be notified about
- Select your channels
- Test the alerts

### 9. Build a Template
- Start from a blank template
- Add your common fields
- Save for reuse

## 📈 Track Your Progress

Use these metrics to measure your success:

- **Time saved:** Track hours saved per week
- **Tasks completed:** Count of completed items
- **Team adoption:** % of team using {name}
- **ROI:** Calculate your return on investment

## Need More Help?

- [User Manual](user-manual.md)
- [Video Tutorials](support-resources.md)
- [Community Forum](support-resources.md)
"""

    def _generate_user_manual(self, product_data: Dict[str, Any]) -> str:
        """Generate user manual"""
        name = product_data.get("name", "Product")
        features = product_data.get("features", [])

        manual = f"""# {name} - User Manual

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Features](#core-features)
3. [Advanced Features](#advanced-features)
4. [Best Practices](#best-practices)
5. [Tips and Tricks](#tips-and-tricks)
6. [Keyboard Shortcuts](#keyboard-shortcuts)
7. [API Reference](#api-reference)
8. [Integrations](#integrations)

## Getting Started

Welcome to {name}! This manual will help you get the most out of the product.

### Key Concepts

- **Workspace:** Your main environment
- **Projects:** Organized units of work
- **Tasks:** Individual items to complete
- **Teams:** Groups of collaborators
- **Reports:** Insights and analytics

### Navigation

- **Dashboard:** Overview of everything
- **Projects:** Manage your work
- **Team:** Collaborate with others
- **Reports:** Analyze your data
- **Settings:** Customize {name}

## Core Features

"""

        for i, feature in enumerate(features[:5], 1):
            manual += f"""### {i}. {feature.get('name', 'Feature')}

{feature.get('description', 'Feature description')}

**How to use:**
1. Navigate to the feature
2. Follow the prompts
3. Save your work

**Tips:**
- Use keyboard shortcuts
- Customize your view
- Share with your team

"""

        manual += """
## Advanced Features

### Automation
Set up automated workflows to save time.

### Custom Fields
Add custom fields to track what matters to you.

### API Access
Integrate {name} with your existing tools.

### Advanced Reporting
Create custom reports and dashboards.

## Best Practices

1. **Start Small:** Begin with one project and expand
2. **Use Templates:** Save time with reusable templates
3. **Collaborate:** Invite your team early
4. **Automate:** Set up workflows for repetitive tasks
5. **Measure:** Track your progress with reports
6. **Iterate:** Continuously improve your process

## Tips and Tricks

- Use keyboard shortcuts to save time
- Set up notifications to stay informed
- Create templates for common tasks
- Use tags to organize your work
- Schedule reports for regular updates
- Archive completed projects

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New Project | Ctrl/Cmd + N |
| Search | Ctrl/Cmd + K |
| Save | Ctrl/Cmd + S |
| Undo | Ctrl/Cmd + Z |
| Redo | Ctrl/Cmd + Shift + Z |
| Help | F1 or ? |

## API Reference

### Base URL
```
https://api.{name.lower()}.com/v1
```

### Endpoints

{api = product_data.get("api", {})}
{endpoints = api.get("endpoints", [])}

"""

        api = product_data.get("api", {})
        endpoints = api.get("endpoints", [])

        for endpoint in endpoints[:10]:
            manual += f"- `{endpoint}`\n"

        manual += """
### Authentication
```
Authorization: Bearer YOUR_API_KEY
```

## Integrations

Connect {name} with your favorite tools:

- Slack
- Microsoft Teams
- Google Workspace
- GitHub
- Jira
- Zapier
- And many more...

## Support

- [FAQ](faq.md)
- [Troubleshooting](troubleshooting.md)
- [Support Resources](support-resources.md)
- [Community Forum](support-resources.md)
"""

        return manual

    def _generate_faq(self, product_data: Dict[str, Any]) -> str:
        """Generate FAQ"""
        name = product_data.get("name", "Product")

        return f"""# {name} - Frequently Asked Questions

## General Questions

### What is {name}?
{product_data.get('description', '{name} is a powerful tool that helps you achieve your goals.')}

### Who is {name} for?
{name} is designed for teams and individuals who want to be more productive and efficient.

### How much does {name} cost?
Please visit our pricing page for the latest information.

### Is there a free trial?
Yes! We offer a 14-day free trial with full access to all features.

## Getting Started

### How do I create an account?
1. Visit our website
2. Click "Sign Up"
3. Enter your email and create a password
4. Verify your email
5. Start using {name}!

### How long does setup take?
Most users are up and running in 15-30 minutes.

### Do I need any technical knowledge?
No! {name} is designed for users of all technical levels.

## Features

### What are the main features?
{name} offers a wide range of features. See the [User Manual](user-manual.md) for details.

### Can I customize {name}?
Yes! {name} is highly customizable. You can:
- Create custom fields
- Build custom workflows
- Customize your dashboard
- Configure notifications

### Does {name} integrate with other tools?
Yes! We integrate with 100+ popular tools including Slack, Microsoft Teams, Google Workspace, and more.

## Billing & Pricing

### How does billing work?
We offer monthly and annual billing. Annual billing saves you 20%.

### Can I change my plan?
Yes! You can upgrade or downgrade your plan at any time.

### Do you offer refunds?
Yes! We offer a 30-day money-back guarantee.

## Security & Privacy

### Is my data secure?
Yes! We use industry-standard encryption and security practices. {name} is SOC 2 Type II certified.

### Where is my data stored?
Your data is stored in secure, geographically distributed data centers.

### Do you share my data?
No! We never share your data with third parties. See our [Privacy Policy](#) for details.

## Support

### How do I get help?
- [Knowledge Base](#)
- [Community Forum](support-resources.md)
- [Email Support](support-resources.md)
- [Live Chat](support-resources.md)

### What are your support hours?
- **Email:** 24/7
- **Live Chat:** Monday-Friday, 9am-5pm EST
- **Phone:** Enterprise customers only

### Do you offer training?
Yes! We offer:
- Video tutorials
- Webinars
- On-site training (Enterprise)
- Custom training programs

## Technical Questions

### What are the system requirements?
- Modern web browser (Chrome, Firefox, Safari, Edge)
- 4GB RAM minimum
- Broadband internet connection

### Does {name} work offline?
Limited offline functionality is available. Most features require an internet connection.

### Can I use {name} on mobile?
Yes! {name} has native iOS and Android apps.

## Troubleshooting

### I'm having trouble logging in
1. Check your email and password
2. Try resetting your password
3. Clear your browser cache
4. Contact support if the issue persists

### {name} is running slowly
1. Check your internet connection
2. Close unnecessary browser tabs
3. Clear your browser cache
4. Try a different browser

### I lost my data
1. Check the trash/recycle bin
2. Restore from backup
3. Contact support for assistance

Still have questions? [Contact us](support-resources.md)
"""

    def _generate_troubleshooting(self, product_data: Dict[str, Any]) -> str:
        """Generate troubleshooting guide"""
        name = product_data.get("name", "Product")

        return f"""# {name} - Troubleshooting Guide

## Common Issues

### Login Problems

**Issue:** Can't log in to {name}

**Solutions:**
1. Verify your email and password
2. Check if Caps Lock is on
3. Reset your password
4. Clear browser cookies and cache
5. Try a different browser
6. Contact support if issue persists

### Performance Issues

**Issue:** {name} is slow or unresponsive

**Solutions:**
1. Check your internet connection
2. Close unnecessary browser tabs
3. Clear browser cache
4. Disable browser extensions
5. Try incognito/private mode
6. Restart your browser

### Data Sync Issues

**Issue:** Data not syncing across devices

**Solutions:**
1. Check your internet connection
2. Force a manual sync
3. Log out and log back in
4. Clear local storage
5. Reinstall the mobile app

### Integration Problems

**Issue:** Third-party integrations not working

**Solutions:**
1. Verify API keys are correct
2. Check integration permissions
3. Review integration logs
4. Reauthorize the connection
5. Contact integration support

## Error Messages

### "Authentication Failed"
- Check your credentials
- Reset your password
- Contact support

### "Server Error"
- Try again in a few minutes
- Check [status page](#)
- Contact support if persistent

### "Permission Denied"
- Check your user role
- Ask your admin for access
- Review permission settings

### "Quota Exceeded"
- Upgrade your plan
- Wait until next billing cycle
- Contact sales

## Getting More Help

If you can't find a solution here:

1. Search the [Knowledge Base](#)
2. Ask the [Community](support-resources.md)
3. [Contact Support](support-resources.md)
4. Report a bug

## Reporting Bugs

When reporting a bug, please include:

- Description of the issue
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshots (if applicable)
- Browser and OS version
- Account ID (don't share password)

## Status Page

Check our [status page](#) for:
- Current system status
- Scheduled maintenance
- Incident history
- Subscribe to notifications
"""

    def _generate_support_resources(self, product_data: Dict[str, Any]) -> str:
        """Generate support resources"""
        name = product_data.get("name", "Product")

        return f"""# {name} - Support Resources

We're here to help you succeed with {name}.

## Help Center

Browse our comprehensive knowledge base:

- [Getting Started](#)
- [User Manual](user-manual.md)
- [FAQ](faq.md)
- [Troubleshooting](troubleshooting.md)
- [Best Practices](#)
- [Video Tutorials](#)

## Community

Join our community to connect with other users:

- [Community Forum](#)
- [Discord Server](#)
- [Reddit](#)
- [Stack Overflow](#)
- [GitHub Discussions](#)

## Direct Support

### Email Support
- **Email:** support@example.com
- **Response time:** Within 24 hours
- **Availability:** 24/7

### Live Chat
- **Hours:** Monday-Friday, 9am-5pm EST
- **Access:** Click the chat icon in the app

### Phone Support (Enterprise)
- **Hours:** Monday-Friday, 9am-5pm EST
- **Number:** 1-800-{name.upper()}-00
- **Available to:** Enterprise customers

### Priority Support (Premium)
- **Response time:** Within 1 hour
- **Availability:** 24/7
- **Includes:** Dedicated account manager

## Training & Education

### Video Tutorials
- [Getting Started Videos](#)
- [Feature Walkthroughs](#)
- [Advanced Techniques](#)
- [Best Practices](#)

### Webinars
- **Weekly Webinars:** Every Wednesday at 2pm EST
- [View Schedule](#)
- [Register](#)
- [Watch Recordings](#)

### Documentation
- [API Documentation](#)
- [Developer Guides](#)
- [Integration Guides](#)
- [Security & Compliance](#)

### Training Programs
- **Self-Paced:** Online courses
- **Instructor-Led:** Virtual and in-person
- **Custom:** Tailored to your team
- [Learn More](#)

## Office Hours

Join our weekly office hours for live Q&A:

- **When:** Every Thursday, 3-4pm EST
- **Where:** [Zoom Link](#)
- **Who:** Product team and customer success

## Consulting Services

Need more hands-on help?

- **Implementation:** Get up and running faster
- **Custom Development:** Tailored solutions
- **Best Practices:** Optimize your setup
- **Training:** Custom programs for your team

[Contact Sales](#)

## Feedback

We love hearing from you!

- [Feature Requests](#)
- [Bug Reports](troubleshooting.md)
- [General Feedback](#)
- [NPS Survey](#)

## Status & Updates

- [System Status](#)
- [Release Notes](#)
- [Roadmap](#)
- [Blog](#)

## Social Media

Follow us for updates and tips:

- Twitter: [@{name}](#)
- LinkedIn: [{name}](#)
- YouTube: [{name} Channel](#)
- Facebook: [{name}](#)
"""

    def _generate_success_metrics(self) -> str:
        """Generate success metrics"""
        return """# Customer Success Metrics

Track these KPIs to measure onboarding success.

## Onboarding Metrics

### Completion Rate
- **Definition:** % of new users who complete onboarding
- **Target:** >80%
- **How to measure:** Track wizard completion

### Time to First Value
- **Definition:** Time from signup to first meaningful action
- **Target:** <15 minutes
- **How to measure:** Track first key action

### Setup Completion
- **Definition:** % of users who complete setup checklist
- **Target:** >70%
- **How to measure:** Track checklist items

## Engagement Metrics

### Daily Active Users (DAU)
- **Definition:** Users active in last 24 hours
- **Target:** >50% of total users
- **How to measure:** Track logins

### Weekly Active Users (WAU)
- **Definition:** Users active in last 7 days
- **Target:** >70% of total users
- **How to measure:** Track logins

### Monthly Active Users (MAU)
- **Definition:** Users active in last 30 days
- **Target:** >80% of total users
- **How to measure:** Track logins

### Session Duration
- **Definition:** Average time per session
- **Target:** >10 minutes
- **How to measure:** Track session time

## Feature Adoption

### Feature Usage Rate
- **Definition:** % of users using each feature
- **Target:** >40% for core features
- **How to measure:** Track feature usage

### Power Users
- **Definition:** % of users using 5+ features
- **Target:** >30%
- **How to measure:** Track feature breadth

### Feature Depth
- **Definition:** Average actions per feature
- **Target:** >10 actions per feature
- **How to measure:** Track feature interactions

## Customer Satisfaction

### Net Promoter Score (NPS)
- **Definition:** Likelihood to recommend (0-10)
- **Target:** >50
- **How to measure:** Survey at day 30

### Customer Satisfaction (CSAT)
- **Definition:** Satisfaction rating (1-5)
- **Target:** >4.0
- **How to measure:** In-app survey

### Customer Effort Score (CES)
- **Definition:** Effort to complete task (1-7)
- **Target:** <3
- **How to measure:** Post-task survey

## Retention Metrics

### Day 1 Retention
- **Definition:** % of users who return next day
- **Target:** >60%
- **How to measure:** Track return visits

### Day 7 Retention
- **Definition:** % of users active after 7 days
- **Target:** >40%
- **How to measure:** Track return visits

### Day 30 Retention
- **Definition:** % of users active after 30 days
- **Target:** >30%
- **How to measure:** Track return visits

### Churn Rate
- **Definition:** % of users who cancel
- **Target:** <5% monthly
- **How to measure:** Track cancellations

## Business Metrics

### Conversion Rate
- **Definition:** % of trial users who convert to paid
- **Target:** >20%
- **How to measure:** Track trial conversions

### Average Revenue Per User (ARPU)
- **Definition:** Average revenue per user
- **Target:** Industry benchmark
- **How to measure:** Calculate from billing

### Customer Lifetime Value (CLV)
- **Definition:** Total revenue per customer
- **Target:** 3x CAC
- **How to measure:** Calculate from billing

### Customer Acquisition Cost (CAC)
- **Definition:** Cost to acquire customer
- **Target:** <1/3 of CLV
- **How to measure:** Calculate from marketing spend

## Reporting

### Weekly Report
- Onboarding completion rate
- Feature adoption
- Support tickets
- NPS score

### Monthly Report
- All metrics
- Trends and insights
- Action items
- Customer feedback

### Quarterly Review
- Strategic metrics
- ROI analysis
- Roadmap alignment
- Customer interviews
"""

    def _generate_communication_plan(self) -> str:
        """Generate communication plan"""
        return """# Customer Communication Plan

## Day 1: Welcome Email
**Goal:** Make a great first impression
**Content:**
- Warm welcome
- Quick start guide
- Support resources
**Channel:** Email
**Owner:** Customer Success

## Day 3: Check-in Email
**Goal:** Ensure smooth onboarding
**Content:**
- How's it going?
- Common questions
- Quick wins to try
**Channel:** Email
**Owner:** Customer Success

## Day 7: Feature Highlights
**Goal:** Drive feature adoption
**Content:**
- Top 3 features
- Video tutorials
- Use cases
**Channel:** Email + In-app
**Owner:** Product Marketing

## Day 14: Success Check
**Goal:** Ensure customer success
**Content:**
- Progress check
- Advanced tips
- Schedule training
**Channel:** Email
**Owner:** Customer Success

## Day 30: Review & Feedback
**Goal:** Gather feedback and improve
**Content:**
- NPS survey
- Feature feedback
- Success stories
**Channel:** Email + Survey
**Owner:** Customer Success

## Day 60: Advanced Training
**Goal:** Deepen product knowledge
**Content:**
- Advanced features
- Best practices
- Webinar invitation
**Channel:** Email
**Owner:** Customer Success

## Day 90: Renewal/Expansion
**Goal:** Drive retention and growth
**Content:**
- Usage report
- ROI analysis
- Upgrade options
**Channel:** Email + Call
**Owner:** Account Manager

## Ongoing Communications

### Weekly Newsletter
- Product updates
- Tips and tricks
- Customer stories
- Upcoming events

### Monthly Webinar
- Feature deep dives
- Customer presentations
- Q&A session

### Quarterly Business Review
- Usage analytics
- ROI report
- Roadmap preview
- Strategic planning

## Communication Channels

### Email
- Primary channel
- Automated sequences
- Personalized outreach

### In-App Messages
- Contextual help
- Feature announcements
- Tips and tricks

### Push Notifications
- Mobile app
- Important updates
- Reminders

### SMS (Optional)
- Critical alerts
- Verification codes
- Premium tier only

### Phone Calls
- High-touch customers
- Enterprise accounts
- Escalations

## Personalization

### Segmentation
- By plan (Free/Pro/Enterprise)
- By industry
- By use case
- By engagement level

### Dynamic Content
- User name
- Company name
- Usage data
- Recommendations

### Behavioral Triggers
- Inactivity alerts
- Feature usage milestones
- Support ticket patterns
- Billing events

## Best Practices

1. **Be Helpful, Not Salesy:** Focus on value
2. **Be Timely:** Send at the right time
3. **Be Personal:** Use customer data
4. **Be Consistent:** Regular cadence
5. **Be Measurable:** Track metrics
6. **Be Iterative:** Continuously improve
"""
