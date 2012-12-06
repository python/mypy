class BankAccount(object):
    void __init__(self, int initial_balance=0):
        self.balance = initial_balance
    void deposit(self, int amount):
        self.balance += amount
    void withdraw(self, int amount):
        self.balance -= amount
    bool overdrawn(self):
        return self.balance < 0
my_account = BankAccount(15)
my_account.withdraw(5)
print(my_account.balance)
