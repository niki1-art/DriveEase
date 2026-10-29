
document.addEventListener("DOMContentLoaded", () => {
  const carCards = document.querySelectorAll(".car-card");
  const searchCar = document.getElementById("searchCar");
  const searchText = document.getElementById("searchText");
  const searchButton = document.getElementById("searchButton");
  const noCars = document.getElementById("noCars");

  const bookingSection = document.getElementById("bookingSection");
  const bookingForm = document.getElementById("bookingForm");
  const selectedCarInput = document.getElementById("carName");
  const selectedCarText = document.getElementById("selectedCarText");
  const pickupInput = document.getElementById("pickupDate");
  const returnInput = document.getElementById("returnDate");
  const message = document.getElementById("bookingMessage");
  const submitButton = document.getElementById("submitBooking");

  // Set the earliest selectable date to today.
  const today = new Date();
  const localToday = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0")
  ].join("-");

  pickupInput.min = localToday;
  returnInput.min = localToday;

  pickupInput.addEventListener("change", () => {
    returnInput.min = pickupInput.value || localToday;

    if (returnInput.value && returnInput.value < returnInput.min) {
      returnInput.value = returnInput.min;
    }
  });

  // Search and filter cars.
  function filterCars() {
    const type = searchCar.value;
    const term = searchText.value.trim().toLowerCase();
    let visibleCount = 0;

    carCards.forEach((card) => {
      const matchesType =
        type === "all" || card.dataset.type === type;
      const matchesName =
        card.dataset.name.toLowerCase().includes(term);
      const visible = matchesType && matchesName;

      card.hidden = !visible;
      if (visible) visibleCount++;
    });

    noCars.hidden = visibleCount !== 0;
  }

  searchButton.addEventListener("click", filterCars);

  searchText.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      filterCars();
    }
  });

  searchCar.addEventListener("change", filterCars);

  // Open the booking form for the selected car.
  document.querySelectorAll(".book-button").forEach((button) => {
    button.addEventListener("click", () => {
      const carName = button.dataset.car;

      bookingForm.reset();
      selectedCarInput.value = carName;
      selectedCarText.textContent = "Selected car: " + carName;
      pickupInput.min = localToday;
      returnInput.min = localToday;
      message.textContent = "";
      message.style.color = "";

      bookingSection.hidden = false;
      bookingSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });

      document.getElementById("customerName").focus({
        preventScroll: true
      });
    });
  });

  // Submit a new booking.
  bookingForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!bookingForm.reportValidity()) return;

    const booking = {
      customerName:
        document.getElementById("customerName").value.trim(),
      customerPhone:
        document.getElementById("customerPhone").value.trim(),
      carName: selectedCarInput.value,
      pickupDate: pickupInput.value,
      returnDate: returnInput.value
    };

    message.style.color = "#164b38";
    message.textContent = "Saving your booking...";
    submitButton.disabled = true;
    submitButton.textContent = "Please wait...";

    try {
      const response = await fetch("/api/bookings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(booking)
      });

      const responseText = await response.text();
      let result;

      try {
        result = JSON.parse(responseText);
      } catch {
        throw new Error(
          "Server returned an invalid response. Check the Flask terminal."
        );
      }

      if (!response.ok) {
        throw new Error(result.error || "Booking could not be saved.");
      }

      message.style.color = "#176c3a";
      message.textContent =
        `${result.message} Booking ID: ${result.bookingId}. ` +
        "Please save your Booking ID to check its status later.";

      bookingForm.reset();
      selectedCarInput.value = booking.carName;
      selectedCarText.textContent = "Selected car: " + booking.carName;
      pickupInput.min = localToday;
      returnInput.min = localToday;

    } catch (error) {
      message.style.color = "#b42318";
      message.textContent =
        "Booking save nahi hui: " + error.message;
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Confirm Booking";
    }
  });

  // Check booking status using Booking ID AND registered mobile number.
  const checkStatusButton =
    document.getElementById("checkBookingStatus");
  const statusIdInput =
    document.getElementById("statusBookingId");
  const statusPhoneInput =
    document.getElementById("statusPhone");
  const statusResult =
    document.getElementById("bookingStatusResult");

  if (
    checkStatusButton &&
    statusIdInput &&
    statusPhoneInput &&
    statusResult
  ) {
    checkStatusButton.addEventListener("click", async () => {
      const bookingId = statusIdInput.value.trim();
      const phone = statusPhoneInput.value.trim();

      if (!bookingId || !/^[1-9][0-9]*$/.test(bookingId)) {
        statusResult.textContent =
          "Please enter a valid Booking ID.";
        return;
      }

      if (!/^[0-9]{10}$/.test(phone)) {
        statusResult.textContent =
          "Please enter your registered 10-digit mobile number.";
        return;
      }

      statusResult.textContent = "Checking your booking...";
      checkStatusButton.disabled = true;

      try {
        const response = await fetch("/api/booking-status", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            bookingId: bookingId,
            phone: phone
          })
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.error ||
            "Booking not found. Check your Booking ID and phone number."
          );
        }

        statusResult.textContent =
          `Booking #${data.bookingId} | ${data.carName} | ` +
          `Pickup: ${data.pickupDate} | Return: ${data.returnDate} | ` +
          `Status: ${data.status}`;

        statusResult.style.color =
          data.status === "Approved" ? "#176c3a" :
          data.status === "Rejected" ? "#b42318" :
          "#805900";

      } catch (error) {
        statusResult.style.color = "#b42318";
        statusResult.textContent = error.message;
      } finally {
        checkStatusButton.disabled = false;
      }
    });
  }
});
