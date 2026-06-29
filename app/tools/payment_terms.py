from datetime import datetime, timedelta
import re


class PaymentTermsCalculator:

    def calculate(
        self,
        invoice_date: str,
        payment_terms: str,
        invoice_amount: float,
    ):

        invoice_date = datetime.strptime(
            invoice_date,
            "%Y-%m-%d",
        )

        payment_terms = payment_terms.strip()

        # -----------------------------
        # Due on Receipt
        # -----------------------------

        if payment_terms.lower() == "due on receipt":

            due_date = invoice_date

            return {
                "payment_terms": payment_terms,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "discount_deadline": None,
                "discount_amount": 0,
                "days_until_due": 0,
            }

        # -----------------------------
        # Net XX
        # -----------------------------

        match = re.match(
            r"Net\s+(\d+)",
            payment_terms,
            re.IGNORECASE,
        )

        if match:

            days = int(match.group(1))

            due_date = invoice_date + timedelta(days=days)

            return {
                "payment_terms": payment_terms,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "discount_deadline": None,
                "discount_amount": 0,
                "days_until_due": days,
            }

        # -----------------------------
        # 2/10 Net 30
        # -----------------------------

        match = re.match(
            r"(\d+)\/(\d+)\s+Net\s+(\d+)",
            payment_terms,
            re.IGNORECASE,
        )

        if match:

            discount_percent = float(match.group(1))

            discount_days = int(match.group(2))

            due_days = int(match.group(3))

            due_date = invoice_date + timedelta(
                days=due_days
            )

            discount_deadline = invoice_date + timedelta(
                days=discount_days
            )

            discount_amount = round(
                invoice_amount
                * (discount_percent / 100),
                2,
            )

            return {
                "payment_terms": payment_terms,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "discount_deadline": discount_deadline.strftime(
                    "%Y-%m-%d"
                ),
                "discount_amount": discount_amount,
                "days_until_due": due_days,
                "days_until_discount": discount_days,
            }

        return {
            "error": "Unsupported Payment Terms"
        }