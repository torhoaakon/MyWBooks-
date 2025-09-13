from mywbooks.factories import webbook_from_url

wb = webbook_from_url("https://www.royalroad.com/fiction/21220")


print(wb.data.title, wb.data.author, wb.data.cover_image)
for ch in wb._chapter_urls:
    print(ch)

# for ch in wb.get_chapters():
#     print(ch.get_content(include_images=False, include_chapter_title=False))
