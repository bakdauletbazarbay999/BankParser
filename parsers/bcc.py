import pdfplumber
import io
import re
from parsers.base import Parser
from models import Payment, ParseError, ParseResult


class BccPdfParser(Parser):
    def can_parse(self, file_bytes: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                # Бірінші беттің мәтінін тексеру
                text = pdf.pages[0].extract_text().lower()
                return "банк центркредит" in text or "bcc business" in text
        except:
            return False

    def parse(self, file_bytes: bytes) -> ParseResult:
        result = ParseResult()
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    # Кестені алу
                    table = page.extract_table()
                    if not table:
                        continue

                    for row in table:
                        # Бос жолдарды немесе тақырып жолдарын өткізіп жіберу
                        if not row or not row[1] or "Күні" in row[1]:
                            continue

                        try:
                            # 1. Күнді алу (Күні / Дата бағаны)
                            # Мәтін ішінен тек 01.10.2025 сияқты форматты іздейміз
                            date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', row[1])
                            if not date_match:
                                continue
                            # Регулярлық өрнекке сәйкес болу үшін нүктелерді сызықшаға ауыстырамыз
                            date = date_match.group(0).replace('.', '-')
                            # Күн форматын YYYY-MM-DD түріне келтіру (міндетті болса)
                            d, m, y = date.split('-')
                            formatted_date = f"{y}-{m}-{d}"


                            # 2. Дебет және Кредит сомаларын алу
                            # Дебет - шығыс (row[7]), Кредит - кіріс (row[8])
                            debit_raw = row[7].replace(',', '.') if row[7] else "0"
                            credit_raw = row[8].replace(',', '.') if row[8] else "0"

                            # Бос орындарды алып тастау
                            debit = float(re.sub(r'[^\d.]', '', debit_raw) or 0)
                            credit = float(re.sub(r'[^\d.]', '', credit_raw) or 0)


                            if debit > 0:
                                amount = debit
                                t_type = "expense"
                            elif credit > 0:
                                amount = credit
                                t_type = "income"
                            else:
                                continue

                            # 3. Мерчант/Корреспондент (row[5]) және Мақсаты (row[11])
                            merchant = row[5].replace('\n', ' ').strip() if row[5] else "Unknown"
                            purpose = row[11].replace('\n', ' ').strip() if row[11] else ""

                            payment = Payment(
                                date=formatted_date,
                                amount=amount,
                                currency="KZT",
                                type=t_type,
                                merchant=f"{merchant} ({purpose[:50]}...)",  # Толық ақпарат үшін
                                bank="BCC"
                            )
                            result.payments.append(payment)

                        except (ValueError, IndexError):
                            continue

        except Exception as e:
            result.errors.append(
                ParseError(row=0, column=0, message=str(e), rawValue="")
            )

        return result
