gsap.from(".pricing-hero", {

    y: 80,

    opacity: 0,

    duration: 1

});


gsap.from(".pricing-card", {

    scale: 0.9,

    opacity: 0.6,

    duration: 1,

    delay: .3,

    ease: "power3.out"

});


gsap.utils.toArray(".faq-item").forEach((item, index) => {

    gsap.from(item, {

        y: 40,

        opacity: 0,

        duration: .8,

        delay: .6 + index * .15

    });

});