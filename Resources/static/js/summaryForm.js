console.log("summaryForm.js loaded");

document.addEventListener("DOMContentLoaded", () => {

    const summaryForm = document.getElementById("summaryForm");

    if (!summaryForm) {
        console.error("summaryForm was not found.");
        return;
    }


    // =========================================
    // LOAD TEMPORARY DRAFT
    // =========================================

    const savedData = localStorage.getItem("chapterSummary");

    if (savedData) {

        try {

            const data = JSON.parse(savedData);

            document.getElementById("bookTitle").value =
                data.bookTitle || "";

            document.getElementById("chapterTitle").value =
                data.chapterTitle || "";

            document.getElementById("mainIdea").value =
                data.mainIdea || "";

            document.getElementById("lessons").value =
                data.lessons || "";

            document.getElementById("concepts").value =
                data.concepts || "";

            document.getElementById("examples").value =
                data.examples || "";

            document.getElementById("actions").value =
                data.actions || "";

            document.getElementById("insight").value =
                data.insight || "";

            console.log("Temporary draft loaded.");

        } catch (error) {

            console.error(
                "Could not read saved summary:",
                error
            );

        }
    }


    // =========================================
    // SAVE TEMPORARY DRAFT
    // =========================================

    summaryForm.addEventListener("submit", function () {

        const data = {

            bookTitle:
                document.getElementById("bookTitle").value.trim(),

            chapterTitle:
                document.getElementById("chapterTitle").value.trim(),

            mainIdea:
                document.getElementById("mainIdea").value.trim(),

            lessons:
                document.getElementById("lessons").value.trim(),

            concepts:
                document.getElementById("concepts").value.trim(),

            examples:
                document.getElementById("examples").value.trim(),

            actions:
                document.getElementById("actions").value.trim(),

            insight:
                document.getElementById("insight").value.trim()
        };


        // Save temporary draft
        localStorage.setItem(
            "chapterSummary",
            JSON.stringify(data)
        );

        console.log("Temporary draft saved:", data);

        // IMPORTANT:
        // Do NOT use preventDefault().
        // Django will now receive the POST normally.
    });


    // =========================================
    // AUTO-DELETE TEMPORARY DRAFT
    // =========================================

    const DRAFT_LIFETIME = 2 * 60 * 1000;


    if (savedData) {

        setTimeout(() => {

            localStorage.removeItem("chapterSummary");

            console.log(
                "Temporary chapter summary draft expired."
            );

        }, DRAFT_LIFETIME);
    }

});


