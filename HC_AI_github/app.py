from flask import Flask, render_template, request, jsonify
import os
import vertexai
from vertexai.preview.generative_models import GenerativeModel
import PyPDF2
import markdown2

# Initialize Flask app
app = Flask(__name__)

# Initialize Vertex AI
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
PROJECT_ID = "winter-cogency-436501-g9"
REGION = "us-central1"
vertexai.init(project=PROJECT_ID, location=REGION)

# Standards data
STANDARDS = {
    'supervisor': {
        'knowledge_required': "This factor answers two questions: What kind and level of knowledge and skills are needed? How are these knowledge/skills used in doing the work?",
        'supervisory_controls': "Includes the extent of control exercised by the supervisor, work assignment details, level of employee autonomy, and work review procedures.",
        'guidelines': "Guides include desk manuals, established procedures, policies, and handbooks. The employee's judgment is required to interpret and apply these guidelines.",
        'scope_and_effect': "Scope covers the general complexity and breadth of the program, including work directed, services delivered, and geographic coverage. Effect covers the impact on mission and program outcomes for various stakeholders.",
        'personal_contacts': "Contacts may involve individuals within the office, organization, or external agencies, with settings ranging from structured to unstructured.",
        'physical_demands': "Includes physical requirements such as climbing, lifting, and other physical exertions, as well as the frequency of these demands.",
        'work_environment': "The physical surroundings, potential risks, and required safety measures, including exposure frequency to unsafe conditions."
    },
    'non_supervisor': {
        'knowledge_required': "Defines the knowledge and skills needed, including application in performing job duties.",
        'supervisory_controls': "Describes how work is assigned and reviewed, including the degree of autonomy and instruction provided to the employee.",
        'guidelines': "Guides range from standard procedures and manuals to broader references requiring interpretation. Employee judgment in applying these is essential.",
        'scope_and_effect': "Scope covers the purpose and breadth of the work. Effect measures the impact on efficiency, effectiveness, and research conclusions.",
        'personal_contacts': "Contacts include internal and external personnel, considering the communication difficulty and setting. Also, specifies the organizational level of contacts.",
        'physical_demands': "Describes physical requirements, such as lifting, climbing, and frequency of exertion required by the job.",
        'work_environment': "Covers potential risks, physical conditions, and safety requirements in the work environment."
    }
}

def call_gemini_flash(prompt):
    """Call Gemini Flash model with given prompt"""
    model = GenerativeModel("gemini-1.5-flash-002")
    response = model.generate_content(
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 1024,
            "top_p": 0.8,
            "top_k": 40
        }
    )
    return response.text

def process_general_description(text):
    """Process the general description using Gemini Flash"""
    prompt = f"""
    Create a detailed job description from these percentage-based tasks:
    {text}
    
    For each task:
    1. Explain specific responsibilities
    2. List required skills
    3. Describe expected outcomes
    4. Mention relevant tools
    
    Keep it concise and professional.
    """
    return call_gemini_flash(prompt)

def extract_pdf_info(pdf_file):
    """Extract information from PDF"""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    
    sections = [
        "Knowledge Required by the Position",
        "Supervisory Controls",
        "Guidelines",
        "Scope and Effect",
        "Personal Contacts and Factor",
        "Physical Demands",
        "Work Environment"
    ]
    
    extracted_info = {}
    for section in sections:
        prompt = f"""
        Extract and summarize key points for '{section}' from this text:
        {text}
        
        Focus on main requirements and be concise.
        """
        response = call_gemini_flash(prompt)
        extracted_info[section] = response
    
    return extracted_info

def generate_section_content(section_name, pdf_content, user_input, standard_info):
    """Generate content for each section"""
    prompt = f"""
    Create a professional description for {section_name} by combining:

    Standard Information: {standard_info}
    
    PDF Content: {pdf_content}
    
    User Input: {user_input}
    
    Provide a clear, concise response incorporating all sources.
    Focus on key points and maintain professional language.
    """
    return call_gemini_flash(prompt)

def analyze_user_input(user_inputs, standards, pdf_content):
    """
    Analyze user's input against standards and position factors.
    Focus on providing coaching to improve user's input.
    """
    prompt = f"""
    Review the user's original input against position standards and factors.

    STANDARDS:
    {standards}

    POSITION FACTORS FROM PDF:
    {pdf_content}

    USER'S ORIGINAL INPUT:
    {user_inputs}

    For each section where the user provided input:
    1. Compare user's input directly to the standards
    2. Identify specific elements from standards that are missing
    3. Note where position factors from PDF should be better addressed
    4. Suggest specific additions or modifications to better meet standards

    Provide coaching on how to improve the user's original input only.
    Focus strictly on comparing user's input against standards and factors.
    Format as clear bullet points under each section.
    
    If a section has no user input, note "No user input provided" and list key points they should include based on standards.
    """
    return call_gemini_flash(prompt)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')
@app.route('/process', methods=['POST'])
def process():
    """Process the form submission"""
    try:
        supervisor_type = request.form['supervisor_type']
        pdf_file = request.files['pdf_file']
        
        # Collect user inputs
        user_inputs = {
            'Knowledge Required by the Position': request.form.get('knowledge_required', ''),
            'Supervisory Controls': request.form.get('supervisory_controls', ''),
            'Guidelines': request.form.get('guidelines', ''),
            'Scope and Effect': request.form.get('scope_and_effect', ''),
            'Personal Contacts and Factor': request.form.get('personal_contacts', ''),
            'Physical Demands': request.form.get('physical_demands', ''),
            'Work Environment': request.form.get('work_environment', '')
        }
        
        # Process general description separately
        general_description = request.form.get('general_description', '')
        if general_description:
            general_analysis = process_general_description(general_description)
        else:
            general_analysis = "No general description provided."
        
        # Extract PDF info
        pdf_info = extract_pdf_info(pdf_file)
        
        # Generate main content
        markdown_output = "# Position Description\n\n"
        markdown_output += "## General Description\n" + general_analysis + "\n\n"
        
        # Process each section
        sections = {
            'knowledge_required': 'Knowledge Required by the Position',
            'supervisory_controls': 'Supervisory Controls',
            'guidelines': 'Guidelines',
            'scope_and_effect': 'Scope and Effect',
            'personal_contacts': 'Personal Contacts and Factor',
            'physical_demands': 'Physical Demands',
            'work_environment': 'Work Environment'
        }
        
        for field_name, section_title in sections.items():
            user_input = request.form.get(field_name, '')
            standard_info = STANDARDS[supervisor_type][field_name]
            pdf_content = pdf_info.get(section_title, '')
            
            section_content = generate_section_content(
                section_title,
                pdf_content,
                user_input,
                standard_info
            )
            
            markdown_output += f"## {section_title}\n{section_content}\n\n"
        
        # Format user inputs for coaching analysis
        formatted_user_inputs = "# Original User Input Analysis\n\n"
        formatted_user_inputs += f"## General Description\n{general_description}\n\n"
        
        for title, content in user_inputs.items():
            if content.strip():
                formatted_user_inputs += f"## {title}\n{content}\n\n"
            else:
                formatted_user_inputs += f"## {title}\nNo user input provided\n\n"
        
        # Add user input coaching section
        markdown_output += "\n# User Input Coaching\n\n"
        coaching_result = analyze_user_input(
            user_inputs=formatted_user_inputs,
            standards=STANDARDS[supervisor_type],
            pdf_content=pdf_info
        )
        
        markdown_output += coaching_result + "\n\n"
        
        # Convert markdown to HTML for display
        html_content = markdown2.markdown(markdown_output)
        
        return render_template('results.html', 
                             results=html_content, 
                             markdown_content=markdown_output)
        
    except Exception as e:
        print(f"Error details: {str(e)}")  # Add detailed error logging
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)