from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_name  = State()
    waiting_phone = State()
    waiting_email = State()


class OrderStates(StatesGroup):
    waiting_payment_screenshot = State()   # ожидание скриншота от клиента


class AdminStates(StatesGroup):
    waiting_payment_link = State()   # ожидание ссылки на оплату от админа
