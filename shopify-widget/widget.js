// This code fetches your live offers and displays them as a mini list on the page

fetch('https://shopify-thankyou-backend.onrender.com/api/offers')
  .then(res => res.json())
  .then(offers => {
    if (!offers.length) return; // Nothing to show

    // Create a container for the offers
    const container = document.createElement('div');
    container.style = `
      background: #fff; 
      border-radius: 16px; 
      box-shadow: 0 2px 12px rgba(0,0,0,0.06);
      padding: 24px; 
      margin: 32px auto; 
      max-width: 350px; 
      text-align: center;
    `;

    // Add a title
    const title = document.createElement('h2');
    title.innerText = 'Special Offers for You!';
    title.style = 'margin-bottom: 20px; font-family: sans-serif;';
    container.appendChild(title);

    offers.forEach(offer => {
      const offerDiv = document.createElement('div');
      offerDiv.style = 'margin-bottom: 18px;';

      offerDiv.innerHTML = `
        <img src="${offer.image}" style="width:70px;height:70px;object-fit:cover;border-radius:8px;"/><br/>
        <strong style="font-size:1.1em;">${offer.title}</strong><br/>
        <span style="color:#da1b60;font-weight:bold;font-size:1.2em;">${offer.price}</span><br/>
        <a href="${offer.url}" target="_blank" style="color:#2a3f91;text-decoration:underline;font-size:1em;">Shop Now</a>
      `;
      container.appendChild(offerDiv);
    });

    // Insert into the Shopify thank-you page (as high as possible)
    document.body.insertBefore(container, document.body.firstChild);
  });
