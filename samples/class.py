import typing


class BankAccount(object):
    def __init__(self, initial_balance: int = 0) -> None:
        self.balance = initial_balance

    def deposit(self, amount: int) -> None:
        self.balance += amount

    def withdraw(self, amount: int) -> None:
        self.balance -= amount

    def overdrawn(self) -> bool:
        return self.balance < 0
my_account = BankAccount(15)
my_account.withdraw(5)
print(my_account.balance)
