from compiler.render_plan import (
    RenderPlan,
    TextOperation,
    RenderStyle,
    ColumnsOperation,
    RenderLine,
    RenderColumn,
    SeparatorOperation,
    QROperation,
    FeedOperation,
    CutOperation
)

plan = RenderPlan(
    printer_id="printer_001",
    operations=[
        TextOperation(
            text="JALDIMAI FOODS",
            style=RenderStyle(
                alignment="center",
                bold=True,
                size="large"
            )
        ),

        SeparatorOperation(
            character="-",
            repeat=48
        ),

        ColumnsOperation(
            lines=[
                RenderLine(
                    columns=[
                        RenderColumn(
                            text="Chicken Momo",
                            width=34,
                            alignment="left"
                        ),
                        RenderColumn(
                            text="Rs. 200",
                            width=14,
                            alignment="right"
                        )
                    ]
                )
            ]
        ),

        QROperation(
            data="https://example.com/order/1024",
            method="native",
            size=6
        ),

        FeedOperation(lines=3),

        CutOperation(mode="full")
    ]
)

for operation in plan.operations:
    print(type(operation).__name__, operation)
