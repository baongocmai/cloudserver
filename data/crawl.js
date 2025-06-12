const fs = require('fs');
const puppeteer = require('puppeteer');
const crypto = require('crypto');

function makeId(title, url) {
  return crypto.createHash('md5').update(title + url).digest('hex');
}

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  const baseURL = "https://cloud.mobifone.vn";

  const categories = [
    { name: "DỊCH VỤ", url: "/Services", selector: "#sub a" },
    { name: "GIỚI THIỆU", url: "/Introduce", selector: "#sub a" },
    { name: "BẢNG GIÁ", url: "/Services", selector: "#sub a" },
    { name: "TIN TỨC", url: "/News", selector: "#sub a" },
    { name: "TÀI LIỆU", url: "/Documents", selector: "#sub a" },
    { name: "CÂU HỎI THƯỜNG GẶP", url: "/Manual", selector: "#sub a" },
    { name: "HƯỚNG DẪN SỬ DỤNG", url: "/Instructions", selector: "#sub a" },
    { name: "LIÊN HỆ", url: "/Contact", selector: "#sub a" },
  ];

  const chunks = [];

  for (const category of categories) {
    console.log(`👉 Đang xử lý danh mục: ${category.name} - ${baseURL + category.url}`);
    await page.goto(`${baseURL}${category.url}`, { waitUntil: 'networkidle2' });

    const links = await page.$$eval(category.selector, as =>
      as
        .map(a => ({
          name: a.innerText.trim(),
          href: a.getAttribute('href')
        }))
        .filter(link => link.href && link.href.trim() !== '')
    );

    for (const { name, href } of links) {
      const fullUrl = href.startsWith('http') ? href : `${baseURL}${href}`;
      console.log(`  - Đang lấy nội dung: ${name} (${fullUrl})`);

      try {
  await page.goto(fullUrl, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(resolve => setTimeout(resolve, 1000));

  const text = await page.evaluate(() => {
    const contentSelectors = ['h1', 'h2', 'h3', 'h4', 'p', 'li'];
    const excludeSelectors = ['header', 'footer', 'nav', '.sidebar', 'script', 'style', '.ads', '.menu'];

    const excludeSet = new Set(excludeSelectors);

    function isExcluded(element) {
      if (!element) return false;
      const tag = element.tagName.toLowerCase();
      if (excludeSet.has(tag)) return true;
      for (const cls of excludeSet) {
        if (cls.startsWith('.') && element.classList.contains(cls.slice(1))) return true;
      }
      if (element.parentElement) return isExcluded(element.parentElement);
      return false;
    }

    const elements = Array.from(document.querySelectorAll(contentSelectors.join(',')));
    const filtered = elements.filter(e => !isExcluded(e));
    return filtered.map(e => e.innerText.trim()).filter(Boolean).join('\n');
  });

  if (text) {
    chunks.push({
      id: makeId(name, fullUrl),
      title: name,
      url: fullUrl,
      category: category.name,
      text: text,
      crawled_at: new Date().toISOString()
    });
  }
} catch (e) {
  console.error(`  ! Lỗi khi lấy nội dung của ${fullUrl}:`, e.message);
}

    }
  }

//   fs.mkdirSync('/VHC/data/crawl/raw', { recursive: true });
  fs.writeFileSync('/VHC/data/crawl/raw/mobifone_chunks.json', JSON.stringify(chunks, null, 2), 'utf-8');
  console.log(`✅ Đã crawl xong ${chunks.length} phần nội dung. Ghi vào mobifone_chunks.json`);

  await browser.close();
})();
