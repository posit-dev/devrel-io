#!/usr/bin/env python3

import os
import polars as pl
from shiny import App, render, ui
from querychat import QueryChat
from chatlas import ChatBedrockAnthropic

df = pl.read_parquet("data/output/all.parquet")

# 1. Create ChatBedrockAnthropic client
# Uses AWS credentials from:
# - aws_profile parameter or AWS_PROFILE environment variable
# - ~/.aws/config and ~/.aws/credentials (boto3 automatically reads these)
# - AWS SSO profiles work automatically
chat = ChatBedrockAnthropic(
    model=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-2")),
    aws_profile=os.getenv("AWS_PROFILE", "posit"),
    system_prompt="You are a helpful assistant for analyzing Developer Relations metrics. "
    "The data includes GitHub events, PyPI downloads, CRAN downloads, "
    "and web analytics across multiple open source projects.",
)

# 2. Provide data source and chat client to QueryChat
qc = QueryChat(df, "devrel_output", client=chat)

app_ui = ui.page_sidebar(
    # 3. Create sidebar chat control
    qc.sidebar(),
    ui.card(
        ui.card_header(ui.output_text("title")),
        ui.output_data_frame("data_table"),
        fill=True,
    ),
    fillable=True,
)


def server(input, output, session):
    # 4. Add server logic (to get reactive data frame and title)
    qc_vals = qc.server()

    # 5. Use the filtered/sorted data frame reactively
    @render.data_frame
    def data_table():
        return qc_vals.df()

    @render.text
    def title():
        return qc_vals.title() or "DevRel I/O QueryChat"


app = App(app_ui, server)
