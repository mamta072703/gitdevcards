import json
import sys
import traceback


try:
    from mcp_server import (
        scrape_github,
        analyze_profile,
        generate_card_html,
        save_card,
    )
except Exception:
    print("IMPORT_ERROR")
    traceback.print_exc()
    sys.exit(1)


def main():
    try:
        print("STEP: scrape_github -> torvalds")
        data = scrape_github("torvalds")
        print("SCRAPE_OK")

        print("STEP: analyze_profile")
        analysis = analyze_profile(data)
        print("ANALYZE_OK")

        print("STEP: generate_card_html")
        html = generate_card_html("torvalds", data, analysis)
        print("GENERATE_OK")

        print("STEP: save_card")
        path = save_card("torvalds", html)
        print("SAVE_OK", path)

        # Print requested fields
        card_theme = analysis.get("card_theme")
        vibe = analysis.get("developer_vibe")
        print("RESULT_CARD_THEME:" + str(card_theme))
        print("RESULT_DEVELOPER_VIBE:" + str(vibe))

    except Exception:
        print("RUNTIME_ERROR")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
