document.addEventListener("DOMContentLoaded", () => {

    console.log("cards.js loaded");


    const cards =
        document.querySelectorAll(".card");


    const downloadButtons =
        document.querySelectorAll(".download-btn");


    const upgradeModal =
        document.getElementById("upgradeModal");


    const closeUpgradeModal =
        document.getElementById("closeUpgradeModal");


    const upgradeOverlay =
        document.getElementById("upgradeOverlay");


    console.log("Cards found:", cards.length);

    console.log(
        "Download buttons found:",
        downloadButtons.length
    );


    /*
    ========================================
    STICKY NOTE COLORS
    ========================================
    */

    const colors = [
        "#FFF3A3",
        "#FFD6A5",
        "#CAFFBF",
        "#BDE0FE",
        "#FFC8DD",
        "#E2F0CB"
    ];


    cards.forEach((card) => {

        const randomIndex =
            Math.floor(
                Math.random() * colors.length
            );

        card.style.backgroundColor =
            colors[randomIndex];

    });


    /*
    ========================================
    CARD NUMBERING
    ========================================
    */

    cards.forEach((card, index) => {

        const number =
            card.querySelector(".card-number");


        if (number) {

            number.textContent =
                String(index + 1)
                    .padStart(2, "0");

        }

    });


    /*
    ========================================
    GET CSRF TOKEN
    ========================================
    */

    function getCookie(name) {

        let cookieValue = null;


        if (document.cookie) {

            const cookies =
                document.cookie.split(";");


            for (let cookie of cookies) {

                cookie = cookie.trim();


                if (
                    cookie.startsWith(
                        name + "="
                    )
                ) {

                    cookieValue =
                        decodeURIComponent(
                            cookie.substring(
                                name.length + 1
                            )
                        );

                    break;

                }

            }

        }


        return cookieValue;

    }


    const csrftoken =
        getCookie("csrftoken");


    /*
    ========================================
    OPEN UPGRADE MODAL
    ========================================
    */

    function openUpgradeModal() {

        if (!upgradeModal) {

            console.error(
                "Upgrade modal not found."
            );

            return;

        }


        upgradeModal.classList.add(
            "active"
        );


        document.body.style.overflow =
            "hidden";

    }


    /*
    ========================================
    CLOSE UPGRADE MODAL
    ========================================
    */

    function closeUpgradeModalFunction() {

        if (!upgradeModal) {
            return;
        }


        upgradeModal.classList.remove(
            "active"
        );


        document.body.style.overflow =
            "";

    }


    if (closeUpgradeModal) {

        closeUpgradeModal.addEventListener(
            "click",
            closeUpgradeModalFunction
        );

    }


    if (upgradeOverlay) {

        upgradeOverlay.addEventListener(
            "click",
            closeUpgradeModalFunction
        );

    }


    /*
    ========================================
    ESCAPE KEY
    ========================================
    */

    document.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "Escape"
            ) {

                closeUpgradeModalFunction();

            }

        }
    );


    /*
    ========================================
    DOWNLOAD CARD
    ========================================
    */

    downloadButtons.forEach(
        (button, index) => {

            button.addEventListener(
                "click",
                async () => {

                    const card =
                        cards[index];


                    if (!card) {

                        console.error(
                            "Card not found."
                        );

                        return;

                    }


                    const downloadUrl =
                        button.dataset.downloadUrl;


                    console.log(
                        "Download URL:",
                        downloadUrl
                    );


                    if (!downloadUrl) {

                        console.error(
                            "Download URL missing."
                        );

                        return;

                    }


                    try {

                        button.disabled =
                            true;


                        button.textContent =
                            "Checking...";


                        /*
                        ========================================
                        ASK DJANGO FOR PERMISSION
                        ========================================
                        */

                        const response =
                            await fetch(
                                downloadUrl,
                                {
                                    method: "POST",

                                    headers: {
                                        "X-CSRFToken":
                                            csrftoken,

                                        "X-Requested-With":
                                            "XMLHttpRequest"
                                    },

                                    credentials:
                                        "same-origin"
                                }
                            );


                        console.log(
                            "Server status:",
                            response.status
                        );


                        if (!response.ok) {

                            throw new Error(
                                `Server returned ${response.status}`
                            );

                        }


                        const data =
                            await response.json();


                        console.log(
                            "Server response:",
                            data
                        );


                        /*
                        ========================================
                        DOWNLOAD DENIED
                        ========================================
                        */

                        if (!data.allowed) {

                            openUpgradeModal();

                            return;

                        }


                        /*
                        ========================================
                        DOWNLOAD ALLOWED
                        ========================================
                        */

                        button.textContent =
                            "Creating...";


                        const canvas =
                            await html2canvas(
                                card,
                                {
                                    scale: 2,

                                    useCORS: true,

                                    backgroundColor:
                                        null
                                }
                            );


                        const image =
                            canvas.toDataURL(
                                "image/png"
                            );


                        /*
                        ========================================
                        CREATE DOWNLOAD
                        ========================================
                        */

                        const link =
                            document.createElement(
                                "a"
                            );


                        const cardNumber =
                            String(index + 1)
                                .padStart(2, "0");


                        link.download =
                            `knowledge-card-${cardNumber}.png`;


                        link.href =
                            image;


                        document.body.appendChild(
                            link
                        );


                        link.click();


                        document.body.removeChild(
                            link
                        );


                        /*
                        ========================================
                        DOWNLOAD COUNT
                        ========================================
                        */

                        if (
                            !data.unlimited
                        ) {

                            console.log(
                                `Downloads used: ${data.downloads_used}/5`
                            );

                        } else {

                            console.log(
                                "Premium user: unlimited downloads."
                            );

                        }

                    } catch (error) {

                        console.error(
                            "Download failed:",
                            error
                        );


                        alert(
                            "Something went wrong while creating the card."
                        );

                    } finally {

                        button.disabled =
                            false;


                        button.textContent =
                            "Download";

                    }

                }
            );

        }
    );

});