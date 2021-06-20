class Helpers:

    @staticmethod
    def format_amount(amount) -> str:
        # Remove .0 by casting to int
        if float(amount) % 1 == 0:
            amount = int(float(amount))

        # Adding prefix + for positive number and 0
        if not str(amount).startswith('+') and float(amount) >= 0:
            amount = str('+{}'.format(amount))

        # return as string
        return str(amount)
