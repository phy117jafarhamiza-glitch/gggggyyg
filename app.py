import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import copy
import random
from io import BytesIO

st.set_page_config(page_title="نظام توليد الأسئلة", layout="centered")
st.title("نظام توليد الأسئلة الامتحانية (النسخة الذكية)")

# --- الإعدادات ---
# تأكد أن اسم ملف الوورد الخاص بالقالب بجانب الكود يحمل هذا الاسم بالضبط
TEMPLATE_FILE = 'template.docx'

def force_rtl(paragraph):
    """إجبار النص على الاتجاه العربي والمحاذاة لليمين بقوة"""
    paragraph.paragraph_format.left_indent = None
    paragraph.paragraph_format.right_indent = None
    paragraph.paragraph_format.first_line_indent = None
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.bidi = True
    if paragraph.runs:
        for run in paragraph.runs:
            run.font.rtl = True

def add_row_copy(table, row_idx):
    """نسخ صف وإضافته لآخر الجدول"""
    if row_idx < 0 or row_idx >= len(table.rows): return
    row_copy = copy.deepcopy(table.rows[row_idx]._tr)
    table._tbl.append(row_copy)

def read_questions(file):
    """قراءة بنك الأسئلة بدقة عالية"""
    doc = Document(file)
    mcq_list = []
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    
    i = 0
    while i < len(lines):
        if "# اختياري" in lines[i]:
            i += 1
            continue
        
        # التأكد من وجود سؤال و 4 خيارات أسفله
        if i + 4 < len(lines):
            q = lines[i]
            opts = lines[i+1:i+5]
            if not any("# اختياري" in opt for opt in opts):
                mcq_list.append({"q": q, "opts": opts})
                i += 5
                continue
        i += 1
    return mcq_list

def generate_exam(mcq_data, template_path, target_count):
    doc = Document(template_path)
    random.shuffle(mcq_data)
    final_questions = mcq_data[:target_count]
    
    q_idx = 0
    current_shuffled_opts = None

    for table in doc.tables:
        # استبعاد أي جدول لا يحتوي على خيارات A و B (مثل جدول الجامعة)
        full_table_text = "".join(cell.text for row in table.rows for cell in row.cells)
        if "A" not in full_table_text or "B" not in full_table_text:
            continue
        
        # === 1. مرحلة توسيع الجدول (إذا كان العدد المطلوب أكبر من القالب) ===
        current_slots = 0
        for row in table.rows:
            row_txt = "".join(c.text for c in row.cells)
            if "A" in row_txt and "B" in row_txt:
                current_slots += 1
        
        if target_count > current_slots:
            needed = target_count - current_slots
            last_q_row_idx = len(table.rows) - 2
            last_opt_row_idx = len(table.rows) - 1
            for _ in range(needed):
                add_row_copy(table, last_q_row_idx)
                add_row_copy(table, last_opt_row_idx)

        # === 2. مرحلة تعبئة الأسئلة والخيارات ===
        for row in table.rows:
            cells = row.cells
            cell_texts = [c.text.strip() for c in cells]
            full_row_text = "".join(cell_texts)

            # هل هذا سطر خيارات؟ (يحتوي A و B)
            if "A" in full_row_text and "B" in full_row_text:
                if current_shuffled_opts:
                    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                    for i, c_text in enumerate(cell_texts):
                        # تنظيف الحرف للتعرف عليه بدقة
                        letter = c_text.replace(":", "").replace(".", "").replace("-", "").strip()
                        if letter in opt_map:
                            idx = opt_map[letter]
                            if i + 1 < len(cells):
                                cells[i+1].text = current_shuffled_opts[idx]
                                for p in cells[i+1].paragraphs: force_rtl(p)
                    
                    q_idx += 1
                    current_shuffled_opts = None
                    if q_idx >= len(final_questions):
                        break

            # إذا لم يكن سطر خيارات، فهو سطر سؤال
            else:
                numbering_cell_idx = -1
                for i, c_text in enumerate(cell_texts):
                    # البحث عن الخلية التي تحتوي على رقم (وهي خلية الترقيم 1- أو 2- إلخ)
                    if any(char.isdigit() for char in c_text) and len(c_text) <= 6:
                        numbering_cell_idx = i
                        break
                
                if numbering_cell_idx != -1 and q_idx < len(final_questions):
                    # إعادة ترقيم السؤال برمجياً لضمان الترتيب السليم
                    cells[numbering_cell_idx].text = f"{q_idx + 1}-"
                    for p in cells[numbering_cell_idx].paragraphs: force_rtl(p)
                    
                    # وضع نص السؤال في الخلية التي تلي الترقيم مباشرة
                    if numbering_cell_idx + 1 < len(cells):
                        target_cell = cells[numbering_cell_idx + 1]
                        target_cell.text = final_questions[q_idx]['q']
                        for p in target_cell.paragraphs: force_rtl(p)
                        
                        current_shuffled_opts = list(final_questions[q_idx]['opts'])
                        random.shuffle(current_shuffled_opts)

    # توحيد حجم الخط لجميع أجزاء المستند
    for p in doc.paragraphs:
        for run in p.runs: run.font.size = Pt(11)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs: run.font.size = Pt(11)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- واجهة المستخدم ---
st.info("تأكد أن بنك الأسئلة يحتوي على سؤال وأسفله 4 خيارات فقط.")
uploaded_bank = st.file_uploader("1. ارفع ملف بنك الأسئلة", type=['docx'])

if uploaded_bank:
    questions = read_questions(uploaded_bank)
    if questions:
        st.success(f"✅ تم العثور على {len(questions)} سؤال في البنك.")
        count = st.number_input("كم سؤال تريد في الامتحان؟", 1, len(questions), len(questions))
        
        if st.button("توليد الامتحان الآن"):
            try:
                output = generate_exam(questions, TEMPLATE_FILE, count)
                st.balloons()
                st.download_button("📥 تحميل ورقة الامتحان", output, "Final_Exam_Ready.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                st.success("تم التوليد بنجاح! حمل الملف وتأكد من الأسئلة.")
            except Exception as e:
                st.error(f"❌ حدث خطأ: {e}")
    else:
        st.warning("⚠️ لم يتم العثور على أسئلة! تأكد أن البنك يحتوي على سطر '# اختياري' قبل الأسئلة.")
