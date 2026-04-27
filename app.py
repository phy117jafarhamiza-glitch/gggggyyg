import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import copy
import random
from io import BytesIO
import re

st.set_page_config(page_title="نظام توليد الأسئلة المطور", layout="centered")
st.title("نظام توليد الأسئلة الامتحانية")

# --- الإعدادات ---
TEMPLATE_FILE = 'template.docx'  # تأكد من تسمية ملف القالب بهذا الاسم

def force_rtl(paragraph):
    """ضبط اتجاه النص من اليمين لليسار"""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.bidi = True
    for run in paragraph.runs:
        run.font.rtl = True

def read_questions(file):
    """قراءة الأسئلة من بنك الأسئلة"""
    doc = Document(file)
    mcq_list = []
    current_mode = None
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if "# اختياري" in line:
            current_mode = "MCQ"; i += 1; continue
        if current_mode == "MCQ" and i + 4 < len(lines):
            q = lines[i]
            opts = lines[i+1:i+5]
            mcq_list.append({"q": q, "opts": opts})
            i += 5
        else:
            i += 1
    return mcq_list

def generate_exam(mcq_data, template_path, target_count):
    """توليد ملف الامتحان وتعبئة الجداول"""
    doc = Document(template_path)
    random.shuffle(mcq_data)
    final_questions = mcq_data[:target_count]
    
    q_idx = 0
    current_shuffled_opts = None

    # البحث في كل جداول المستند
    for table in doc.tables:
        for row in table.rows:
            cells = row.cells
            row_text = " ".join([c.text.strip() for c in cells])

            # 1. البحث عن خلية السؤال (تحتوي على رقم مثل 1-)
            # نستخدم regex للبحث عن رقم في بداية الخلية
            match_q = re.search(r'(\d+)-', row_text)
            if match_q and q_idx < len(final_questions):
                # إذا وجدنا الترقيم، نبحث عن الخلية الفارغة المجاورة له لنضع السؤال
                for i, cell in enumerate(cells):
                    if re.search(r'\d+-', cell.text):
                        if i + 1 < len(cells): # نضع السؤال في الخلية التالية
                            cells[i+1].text = final_questions[q_idx]['q']
                            force_rtl(cells[i+1].paragraphs[0])
                            # نجهز الخيارات للسؤال الحالي
                            current_shuffled_opts = list(final_questions[q_idx]['opts'])
                            random.shuffle(current_shuffled_opts)
                            break
                continue

            # 2. البحث عن صف الخيارات (يحتوي على A و B)
            if "A" in row_text and "B" in row_text and current_shuffled_opts:
                opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                for i, cell in enumerate(cells):
                    clean_text = cell.text.strip().replace(":", "").replace(".", "")
                    if clean_text in opt_map:
                        idx = opt_map[clean_text]
                        if i + 1 < len(cells):
                            cells[i+1].text = current_shuffled_opts[idx]
                            force_rtl(cells[i+1].paragraphs[0])
                
                q_idx += 1 # ننتقل للسؤال التالي بعد تعبئة خياراته
                current_shuffled_opts = None

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- واجهة المستخدم ---
uploaded_bank = st.file_uploader("1. ارفع ملف بنك الأسئلة (2.docx)", type=['docx'])

if uploaded_bank:
    questions = read_questions(uploaded_bank)
    if questions:
        st.success(f"✅ تم العثور على {len(questions)} سؤال في البنك.")
        count = st.number_input("كم سؤال تريد توليده؟", 1, len(questions), len(questions))
        
        if st.button("توليد الامتحان الآن"):
            try:
                # محاولة تشغيل التوليد
                output = generate_exam(questions, TEMPLATE_FILE, count)
                st.download_button("📥 تحميل الملف الجاهز", output, "Final_Exam.docx")
            except Exception as e:
                st.error(f"❌ لم يجد التطبيق ملف القالب باسم {TEMPLATE_FILE}. تأكد من رفعه بجانب الكود.")
    else:
        st.warning("⚠️ لم يتم العثور على أسئلة. تأكد أن البنك يحتوي على سطر '# اختياري' قبل الأسئلة.")
