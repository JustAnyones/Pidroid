from discord import ui, TextStyle

from pidroid.models.view import PidroidModal

class ReasonModal(PidroidModal, title='Provide custom reason'):
    reason_input: ui.TextInput["ReasonModal"] = ui.TextInput(
        label="Reason",
        placeholder="Please provide the custom punishment reason.",
        max_length=480,
        style=TextStyle.paragraph
    )

class LengthModal(PidroidModal, title='Provide custom length'):
    length_input: ui.TextInput["LengthModal"] = ui.TextInput(
        label="Length",
        placeholder="Please provide the custom punishment length (e.g. 1h, 30m, 2d, etc.)",
        max_length=120
    )

class DeleteMessageDaysModal(PidroidModal, title='Provide the days'):
    length_input: ui.TextInput["LengthModal"] = ui.TextInput(
        label="Days",
        placeholder="Please provide how from how many days the messages should be deleted (between 0 and 7)",
        max_length=1,
        required=True,
    )
