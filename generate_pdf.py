import sys
from md2pdf.core import md2pdf

def main():
    try:
        md_file = "ORBITA_IQ_PROJECT_STATUS_REPORT.md"
        pdf_file = "ORBITA_IQ_PROJECT_STATUS_REPORT.pdf"
        md2pdf(pdf_file, md_content=open(md_file, "r", encoding="utf-8").read(),
               md_file_path=md_file, css_file_path=None, base_url=None)
        print("Done generating PDF.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
